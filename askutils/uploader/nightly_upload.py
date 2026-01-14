#!/usr/bin/env python3
import os
import sys
import time
import glob
import ftplib
import tempfile
import random
from datetime import datetime, timedelta
from askutils import config
from typing import Optional, List, Tuple
import hashlib

# Influx Writer (wie bei raspi_status)
try:
    from askutils.utils import influx_writer
except Exception:
    influx_writer = None

# === Konfigurierbare Defaults ===
MIN_FILE_AGE_MINUTES = getattr(config, "NIGHTLY_MIN_FILE_AGE_MINUTES", 5)
STABLE_WINDOW_SECONDS = getattr(config, "NIGHTLY_STABLE_WINDOW_SECONDS", 90)

# "Ready"-Retries (Datei wird noch geschrieben)
MAX_READY_RETRIES = getattr(config, "NIGHTLY_MAX_RETRIES", 5)
READY_RETRY_SLEEP_SECONDS = getattr(config, "NIGHTLY_RETRY_SLEEP_SECONDS", 600)

# Upload-Retries (FTP-Fehler)
UPLOAD_MAX_RETRIES = int(getattr(config, "NIGHTLY_UPLOAD_MAX_RETRIES", 5))
UPLOAD_RETRY_MIN_SECONDS = int(getattr(config, "NIGHTLY_UPLOAD_RETRY_MIN_SECONDS", 300))
UPLOAD_RETRY_MAX_SECONDS = int(getattr(config, "NIGHTLY_UPLOAD_RETRY_MAX_SECONDS", 900))

# Initial Jitter (z.B. 30 min = 1800 Sekunden)
NIGHTLY_UPLOAD_JITTER_MAX_SECONDS = int(getattr(config, "NIGHTLY_UPLOAD_JITTER_MAX_SECONDS", 1800))

# FTP-Connect/Login-Retries (separat von Upload-Retries)
CONNECT_MAX_RETRIES = int(getattr(config, "NIGHTLY_CONNECT_MAX_RETRIES", 8))
CONNECT_RETRY_MIN_SECONDS = int(getattr(config, "NIGHTLY_CONNECT_RETRY_MIN_SECONDS", 20))
CONNECT_RETRY_MAX_SECONDS = int(getattr(config, "NIGHTLY_CONNECT_RETRY_MAX_SECONDS", 180))
FTP_TIMEOUT_SECONDS = int(getattr(config, "NIGHTLY_FTP_TIMEOUT_SECONDS", 60))


# ---------------------------------------------------------------------
# Logging (1 Zeile, Datum+Zeit, ohne Sonderzeichen)
# ---------------------------------------------------------------------
def _sanitize_ascii(s: str) -> str:
    try:
        return s.encode("ascii", errors="ignore").decode("ascii", errors="ignore")
    except Exception:
        return "".join(ch for ch in s if ord(ch) < 128)


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = _sanitize_ascii(str(msg).replace("\n", " ").replace("\r", " ")).strip()
    print(f"{ts} {line}", flush=True)


# ---------------------------------------------------------------------
# Influx Status
# measurement=uploadstatus
# tag kamera=ASKxxx, host=host1, asset=<...>
# field nightlyupload = 1/2/3/4
# ---------------------------------------------------------------------
def _log_nightly_status(value: int, asset: str):
    try:
        if influx_writer is None:
            return
        kamera_id = getattr(config, "KAMERA_ID", None) or getattr(config, "KAMERA", None)
        if not kamera_id:
            return
        influx_writer.log_metric(
            "uploadstatus",
            {"nightlyupload": float(value)},
            tags={"host": "host1", "kamera": str(kamera_id), "asset": str(asset)},
        )
    except Exception:
        pass


# ---------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------
def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _is_age_ok(path: str, min_minutes: int) -> bool:
    try:
        mtime = os.path.getmtime(path)
    except FileNotFoundError:
        return False
    age_minutes = (time.time() - mtime) / 60.0
    return age_minutes >= min_minutes


def _is_size_stable(path: str, window_sec: int, poll_sec: int = 5) -> bool:
    if window_sec <= 0:
        try:
            return os.path.getsize(path) > 0
        except FileNotFoundError:
            return False

    try:
        last = os.path.getsize(path)
    except FileNotFoundError:
        return False

    stable_start = time.time()

    while True:
        time.sleep(min(poll_sec, max(1, window_sec)))
        try:
            now_size = os.path.getsize(path)
        except FileNotFoundError:
            log("file_missing_during_stability_check")
            return False

        if now_size != last:
            last = now_size
            stable_start = time.time()

        elapsed = time.time() - stable_start
        if elapsed >= window_sec and now_size > 0:
            return True


def _file_ready(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    if not _is_age_ok(path, MIN_FILE_AGE_MINUTES):
        return False
    if not _is_size_stable(path, STABLE_WINDOW_SECONDS):
        return False
    return True


def _latest_multi(patterns: List[str]) -> Optional[str]:
    all_files = []
    for pat in patterns:
        all_files.extend(glob.glob(pat))
    if not all_files:
        return None
    all_files.sort(key=lambda p: os.path.getmtime(p))
    return all_files[-1]


def _choose_newest_existing(*candidates: str) -> Optional[str]:
    files = [p for p in candidates if p and os.path.isfile(p)]
    if not files:
        return None
    return max(files, key=lambda p: os.path.getmtime(p))


def _png_to_temp_jpg_named(png_path: str) -> str:
    try:
        from PIL import Image
    except ImportError as e:
        raise RuntimeError("pillow_missing_install_pip_install_pillow") from e

    base_noext = os.path.splitext(os.path.basename(png_path))[0]
    fd, tmp_path = tempfile.mkstemp(prefix=f"{base_noext}_", suffix=".jpg")
    os.close(fd)

    img = Image.open(png_path)

    if img.mode in ("RGBA", "LA") or ("transparency" in getattr(img, "info", {})):
        img = img.convert("RGBA")
        bg = Image.new("RGBA", img.size, (0, 0, 0, 255))
        img = Image.alpha_composite(bg, img).convert("RGB")
    else:
        img = img.convert("RGB")

    img.save(tmp_path, format="JPEG", quality=90, optimize=True)
    return tmp_path


def _ensure_uploadable_jpg(local_path: str) -> Tuple[str, Optional[str]]:
    ext = os.path.splitext(local_path)[1].lower()
    if ext == ".png":
        tmp = _png_to_temp_jpg_named(local_path)
        return tmp, tmp
    return local_path, None


def _apply_initial_jitter(date_str: str):
    """
    Deterministischer Jitter: verteilt Kameras stabil über ein Zeitfenster.
    Dadurch entstehen keine 'Wellen' durch zufällige Kollisionen.
    """
    window = int(getattr(config, "NIGHTLY_UPLOAD_JITTER_MAX_SECONDS", 3600))
    if window <= 0:
        return

    kamera_id = getattr(config, "KAMERA_ID", None) or getattr(config, "KAMERA", None) or "UNKNOWN"
    seed = f"{kamera_id}|{date_str}".encode("utf-8")

    h = hashlib.sha256(seed).hexdigest()
    slot = int(h[:8], 16) % window

    log(f"nightly_jitter_deterministic slot_seconds={slot} window_seconds={window}")
    if slot > 0:
        time.sleep(slot)


def _sleep_retry_window(min_s: int, max_s: int):
    if max_s < min_s:
        max_s = min_s
    delay = random.randint(min_s, max_s)
    log(f"nightly_upload_retry_sleep_seconds={delay}")
    time.sleep(delay)


def _connect_ftp_with_retries() -> ftplib.FTP:
    """
    FTP Connect + Login + CWD mit Retries.
    Das fängt Server-Limits und gleichzeitige Logins besser ab als nur Upload-Retries.
    """
    last_err = None

    for attempt in range(1, CONNECT_MAX_RETRIES + 1):
        ftp = None
        try:
            log(f"ftp_connect_try attempt={attempt} server={getattr(config,'FTP_SERVER','')}")
            ftp = ftplib.FTP(timeout=FTP_TIMEOUT_SECONDS)

            # connect getrennt, damit Timeout sauber greift
            ftp.connect(config.FTP_SERVER)

            ftp.login(config.FTP_USER, config.FTP_PASS)
            ftp.cwd(config.FTP_REMOTE_DIR)

            log("ftp_connected")
            return ftp

        except Exception as e:
            last_err = e
            log(f"ftp_connect_failed attempt={attempt} err={e}")

            # Aufräumen
            try:
                if ftp is not None:
                    ftp.quit()
            except Exception:
                try:
                    if ftp is not None:
                        ftp.close()
                except Exception:
                    pass

            if attempt >= CONNECT_MAX_RETRIES:
                break

            _sleep_retry_window(CONNECT_RETRY_MIN_SECONDS, CONNECT_RETRY_MAX_SECONDS)

    raise RuntimeError(f"ftp_connect_giving_up err={last_err}")


def _upload_file_as(
    ftp: ftplib.FTP, local_path: str, remote_subdir: str, root_dir: str, remote_base_name: str
):
    try:
        ftp.cwd(remote_subdir)
    except ftplib.error_perm:
        log(f"remote_dir_create={remote_subdir}")
        ftp.mkd(remote_subdir)
        ftp.cwd(remote_subdir)

    tmp_name = f".{remote_base_name}.uploading"

    log(f"upload_start local={local_path} remote=/{root_dir}/{remote_subdir}/{remote_base_name}")
    with open(local_path, "rb") as f:
        ftp.storbinary(f"STOR {tmp_name}", f)

    try:
        ftp.rename(tmp_name, remote_base_name)
    except Exception:
        try:
            ftp.delete(tmp_name)
        except Exception:
            pass
        raise

    log(f"upload_ok remote=/{remote_subdir}/{remote_base_name}")
    ftp.cwd("..")


def _remote_name_for(local_path: str, date_str: str, *, for_startrail_video: bool = False) -> Optional[str]:
    base = os.path.basename(local_path)
    low = base.lower()
    ext = os.path.splitext(low)[1]

    if for_startrail_video and ext in (".mp4", ".webm") and "startrail_timelapse" in low:
        return f"startrail_timelapse-{date_str}{ext}"

    if ext in (".jpg", ".png") and "startrail" in low:
        return f"startrails-{date_str}.jpg"
    if ext in (".jpg", ".png") and "keogram" in low:
        return f"keogram-{date_str}.jpg"
    if ext in (".jpg", ".png") and "analemma" in low:
        return None

    if ext in (".mp4", ".webm") and ("timelapse" in low or "allsky" in low):
        return f"allsky-{date_str}{ext}"

    return None


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
def upload_nightly_batch(date_str: str = None) -> bool:
    if date_str is None:
        date_str = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    log(f"nightly_start date={date_str}")

    images_base = os.path.join(config.ALLSKY_PATH, config.IMAGE_BASE_PATH)
    analemma_base = os.path.join(config.A_PATH)

    indi_flag = _truthy(getattr(config, "INDI", 0))

    # Dateienliste: (asset, local_path, remote_subdir, forced_remote_name_or_None)
    files: List[Tuple[str, Optional[str], str, Optional[str]]] = []

    if not indi_flag:
        mp4_path = os.path.join(images_base, date_str, f"allsky-{date_str}.mp4")
        webm_path = os.path.join(images_base, date_str, f"allsky-{date_str}.webm")
        video = mp4_path if os.path.isfile(mp4_path) else (webm_path if os.path.isfile(webm_path) else None)

        keo_jpg = os.path.join(images_base, date_str, "keogram", f"keogram-{date_str}.jpg")
        keo_png = os.path.join(images_base, date_str, "keogram", f"keogram-{date_str}.png")
        st_jpg = os.path.join(images_base, date_str, "startrails", f"startrails-{date_str}.jpg")
        st_png = os.path.join(images_base, date_str, "startrails", f"startrails-{date_str}.png")

        keo = _choose_newest_existing(keo_jpg, keo_png)
        st = _choose_newest_existing(st_jpg, st_png)

        a_used = _choose_newest_existing(
            os.path.join(analemma_base, f"analemma-{date_str}_used.jpg"),
            os.path.join(analemma_base, f"analemma-{date_str}_used.png"),
        )
        a_unused = _choose_newest_existing(
            os.path.join(analemma_base, f"analemma-{date_str}_unused.jpg"),
            os.path.join(analemma_base, f"analemma-{date_str}_unused.png"),
        )

        if video:
            files.append(("video", video, config.FTP_VIDEO_DIR, None))
        if keo:
            files.append(("keogram", keo, config.FTP_KEOGRAM_DIR, f"keogram-{date_str}.jpg"))
        if st:
            files.append(("startrail", st, config.FTP_STARTRAIL_DIR, f"startrails-{date_str}.jpg"))
        if a_used:
            files.append(
                (
                    ("analemma_used"),
                    a_used,
                    config.FTP_ANALEMMA_DIR,
                    os.path.basename(a_used).replace(".png", ".jpg"),
                )
            )
        if a_unused:
            files.append(
                (
                    ("analemma_unused"),
                    a_unused,
                    config.FTP_ANALEMMA_DIR,
                    os.path.basename(a_unused).replace(".png", ".jpg"),
                )
            )

    else:
        cam_id = getattr(config, "CAMERAID", None)
        if not cam_id:
            log("indi_enabled_but_cameraid_missing")
            _log_nightly_status(2, "batch")
            return False

        indi_cam_dir = os.path.join(images_base, cam_id)
        if not os.path.isdir(indi_cam_dir):
            log(f"indi_dir_missing dir={indi_cam_dir}")
            _log_nightly_status(2, "batch")
            return False

        date_dir = os.path.join(indi_cam_dir, "timelapse", date_str)

        keo = _latest_multi(
            [
                os.path.join(date_dir, f"allsky-keogram_*_{date_str}_night_*.jpg"),
                os.path.join(date_dir, f"allsky-keogram_*_{date_str}_night_*.png"),
            ]
        )
        st = _latest_multi(
            [
                os.path.join(date_dir, f"allsky-startrail_*_{date_str}_night_*.jpg"),
                os.path.join(date_dir, f"allsky-startrail_*_{date_str}_night_*.png"),
            ]
        )
        tl = _latest_multi(
            [
                os.path.join(date_dir, f"allsky-timelapse_*_{date_str}_night_*.mp4"),
                os.path.join(date_dir, f"allsky-timelapse_*_{date_str}_night_*.webm"),
            ]
        )
        stv = _latest_multi(
            [
                os.path.join(date_dir, f"allsky-startrail_timelapse_*_{date_str}_night_*.mp4"),
                os.path.join(date_dir, f"allsky-startrail_timelapse_*_{date_str}_night_*.webm"),
            ]
        )

        startrailsvideo_dir = getattr(config, "FTP_STARTRAILSVIDEO_DIR", "startrailsvideo")

        if tl:
            files.append(("video", tl, config.FTP_VIDEO_DIR, None))
        if keo:
            files.append(("keogram", keo, config.FTP_KEOGRAM_DIR, f"keogram-{date_str}.jpg"))
        if st:
            files.append(("startrail", st, config.FTP_STARTRAIL_DIR, f"startrails-{date_str}.jpg"))
        if stv:
            files.append(("startrail_video", stv, startrailsvideo_dir, None))

        a_used = _choose_newest_existing(
            os.path.join(analemma_base, f"analemma-{date_str}_used.jpg"),
            os.path.join(analemma_base, f"analemma-{date_str}_used.png"),
        )
        a_unused = _choose_newest_existing(
            os.path.join(analemma_base, f"analemma-{date_str}_unused.jpg"),
            os.path.join(analemma_base, f"analemma-{date_str}_unused.png"),
        )

        if a_used:
            files.append(
                (
                    ("analemma_used"),
                    a_used,
                    config.FTP_ANALEMMA_DIR,
                    os.path.basename(a_used).replace(".png", ".jpg"),
                )
            )
        if a_unused:
            files.append(
                (
                    ("analemma_unused"),
                    a_unused,
                    config.FTP_ANALEMMA_DIR,
                    os.path.basename(a_unused).replace(".png", ".jpg"),
                )
            )

    # Initial Jitter (einmal pro Batch)
    _apply_initial_jitter(date_str)

    try:
        ftp = _connect_ftp_with_retries()
        try:
            for asset, local_path, remote_subdir, forced_remote_name in files:
                log(f"check asset={asset} path={local_path}")

                if not local_path or not os.path.isfile(local_path):
                    log(f"file_missing asset={asset} path={local_path}")
                    _log_nightly_status(3, asset)
                    continue

                # Ready-Checks (Datei wird evtl noch geschrieben)
                attempt = 0
                while attempt <= MAX_READY_RETRIES and not _file_ready(local_path):
                    if attempt == MAX_READY_RETRIES:
                        log(f"file_not_ready asset={asset} path={local_path}")
                        _log_nightly_status(4, asset)
                        break
                    wait = READY_RETRY_SLEEP_SECONDS * (attempt + 1)
                    log(f"not_ready_wait asset={asset} attempt={attempt+1} wait_seconds={wait}")
                    time.sleep(wait)
                    attempt += 1

                if attempt > MAX_READY_RETRIES or not _file_ready(local_path):
                    continue

                # Upload mit Upload-Retries (FTP-Fehler)
                upload_attempt = 0
                while True:
                    upload_attempt += 1
                    temp_jpg = None
                    upload_path = local_path
                    ext = os.path.splitext(local_path)[1].lower()

                    try:
                        if ext in (".jpg", ".png"):
                            upload_path, temp_jpg = _ensure_uploadable_jpg(local_path)

                        remote_base = forced_remote_name if forced_remote_name else os.path.basename(upload_path)

                        _upload_file_as(ftp, upload_path, remote_subdir, config.FTP_REMOTE_DIR, remote_base)

                        # Optionales Remote-Rename fuer Videos
                        lp = os.path.basename(local_path).lower()
                        is_startrail_video = (
                            lp.endswith((".mp4", ".webm")) and "startrail_timelapse" in lp and indi_flag
                        )

                        if os.path.splitext(lp)[1] in (".mp4", ".webm"):
                            desired = _remote_name_for(local_path, date_str, for_startrail_video=is_startrail_video)
                            if desired:
                                prev = ftp.pwd()
                                ftp.cwd(remote_subdir)

                                src = os.path.basename(upload_path)
                                if src != desired:
                                    log(f"remote_rename asset={asset} src={src} dst={desired}")
                                    try:
                                        ftp.rename(src, desired)
                                    except ftplib.error_perm:
                                        try:
                                            ftp.delete(desired)
                                            ftp.rename(src, desired)
                                        except Exception as e2:
                                            log(f"remote_rename_failed asset={asset} err={e2}")

                                ftp.cwd(prev)

                        _log_nightly_status(1, asset)
                        break

                    except Exception as e:
                        log(f"upload_failed asset={asset} attempt={upload_attempt} err={e}")

                        if upload_attempt > UPLOAD_MAX_RETRIES:
                            log(f"giving_up asset={asset} attempts={upload_attempt}")
                            _log_nightly_status(2, asset)
                            break

                        # Wenn die Verbindung gestorben ist: reconnect
                        try:
                            ftp.voidcmd("NOOP")
                        except Exception:
                            log("ftp_noop_failed_reconnect")
                            try:
                                ftp.close()
                            except Exception:
                                pass
                            ftp = _connect_ftp_with_retries()

                        _sleep_retry_window(UPLOAD_RETRY_MIN_SECONDS, UPLOAD_RETRY_MAX_SECONDS)

                    finally:
                        if temp_jpg and os.path.isfile(temp_jpg):
                            try:
                                os.remove(temp_jpg)
                            except Exception:
                                pass

            log("nightly_done")
            _log_nightly_status(1, "batch")
            return True

        finally:
            try:
                ftp.quit()
            except Exception:
                try:
                    ftp.close()
                except Exception:
                    pass

    except Exception as e:
        log(f"nightly_batch_failed err={e}")
        _log_nightly_status(2, "batch")
        return False
