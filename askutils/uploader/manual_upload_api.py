import base64
import glob
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests

from askutils import config

try:
    from askutils.ASKsecret import API_KEY
except Exception:
    API_KEY = None


# ---------------------------------------------------------------------
# Fester Nightly-API-Endpunkt
# ---------------------------------------------------------------------
_DEFAULT_ENC_NIGHTLY_UPLOAD_API_URL = (
    "aHR0cHM6Ly9hbGxza3lrYW1lcmEuc3BhY2UvYXBpL3YxL25pZ2h0bHlfdXBsb2FkLnBocA=="
)

# ---------------------------------------------------------------------
# Feste Zielbreiten
# ---------------------------------------------------------------------
FULLHD_WIDTH = 1920
MOBILE_WIDTH = 960
THUMB_WIDTH = 480

# Sehr hohe JPEG-Qualitaet
JPEG_QSCALE = 2

# Video-Encoding: erster praxistauglicher Startwert
VIDEO_CRF = 24
VIDEO_PRESET = "veryfast"
VIDEO_CODEC = "libx264"
VIDEO_PIXEL_FORMAT = "yuv420p"

HTTP_CONNECT_TIMEOUT = 20
HTTP_READ_TIMEOUT = 300
HTTP_VERIFY_SSL = True


# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------
def log(msg: str) -> None:
    t = datetime.now().strftime("%H:%M:%S")
    print(f"[{t}] {msg}", flush=True)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _latest(glob_pattern: str) -> Optional[str]:
    cand = glob.glob(glob_pattern)
    if not cand:
        return None
    cand.sort(key=lambda p: os.path.getmtime(p))
    return cand[-1]


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


def _file_available(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    try:
        return os.path.getsize(path) > 0
    except OSError:
        return False


def _get_api_url() -> Optional[str]:
    try:
        url = base64.b64decode(_DEFAULT_ENC_NIGHTLY_UPLOAD_API_URL).decode().strip()
    except Exception:
        return None

    if not url.startswith("https://"):
        raise RuntimeError("Nightly upload API must use HTTPS")

    return url


def _ffmpeg_exists() -> bool:
    return shutil.which("ffmpeg") is not None


def _build_scale_filter(max_width: int) -> str:
    return f"scale='if(gt(iw,{max_width}),{max_width},iw)':-2"


# ---------------------------------------------------------------------
# Bild-Reduktion
# ---------------------------------------------------------------------
def _create_jpeg_derivative(src: str, dst: str, width: int) -> None:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-i", src,
        "-frames:v", "1",
        "-vf", _build_scale_filter(width),
        "-q:v", str(JPEG_QSCALE),
        "-pix_fmt", "yuvj420p",
        "-map_metadata", "-1",
        dst,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not os.path.isfile(dst) or os.path.getsize(dst) <= 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"ffmpeg_jpeg_failed: {stderr}")


def _create_three_variants(src: str, tmp_dir: str, prefix: str) -> Dict[str, str]:
    out = {
        "fullhd": os.path.join(tmp_dir, f"{prefix}_fullhd.jpg"),
        "mobile": os.path.join(tmp_dir, f"{prefix}_mobile.jpg"),
        "thumb": os.path.join(tmp_dir, f"{prefix}_thumb.jpg"),
    }

    _create_jpeg_derivative(src, out["fullhd"], FULLHD_WIDTH)
    _create_jpeg_derivative(src, out["mobile"], MOBILE_WIDTH)
    _create_jpeg_derivative(src, out["thumb"], THUMB_WIDTH)

    return out


# ---------------------------------------------------------------------
# Video-Reduktion + Thumb aus Mitte
# ---------------------------------------------------------------------
def _get_video_duration_seconds(video_path: str) -> float:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("ffprobe_failed")

    try:
        return max(0.0, float(result.stdout.strip()))
    except Exception as e:
        raise RuntimeError("ffprobe_duration_parse_failed") from e


def _reduce_video_to_fullhd(src: str, dst: str) -> None:
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", src,
        "-vf", _scale_filter(FULLHD_WIDTH),
        "-c:v", "libx264",
        "-preset", VIDEO_PRESET,
        "-crf", str(VIDEO_CRF),
        "-pix_fmt", "yuv420p",
        "-profile:v", "main",
        "-level", "4.0",
        "-movflags", "+faststart",
        "-an",
        dst
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not os.path.isfile(dst) or os.path.getsize(dst) <= 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"ffmpeg_video_failed: {stderr}")


def _create_video_thumb_from_middle(video_path: str, dst_jpg: str) -> None:
    duration = _get_video_duration_seconds(video_path)
    middle = max(0.0, duration / 2.0)

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-ss", f"{middle:.3f}",
        "-i", video_path,
        "-frames:v", "1",
        "-vf", _build_scale_filter(MOBILE_WIDTH),
        "-q:v", str(JPEG_QSCALE),
        "-pix_fmt", "yuvj420p",
        "-map_metadata", "-1",
        dst_jpg,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not os.path.isfile(dst_jpg) or os.path.getsize(dst_jpg) <= 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"ffmpeg_video_thumb_failed: {stderr}")


def _prepare_video_and_thumb(src_video: str, tmp_dir: str) -> Tuple[str, str]:
    src_ext = os.path.splitext(src_video)[1].lower()
    if src_ext not in (".mp4", ".webm"):
        raise RuntimeError(f"unsupported_video_extension: {src_ext}")

    out_video = os.path.join(tmp_dir, f"video_reduced{src_ext}")
    out_thumb = os.path.join(tmp_dir, "video_thumb.jpg")

    _reduce_video_to_fullhd(src_video, out_video)
    _create_video_thumb_from_middle(out_video, out_thumb)

    return out_video, out_thumb


# ---------------------------------------------------------------------
# HTTPS Upload
# ---------------------------------------------------------------------
def _post_triple_jpg(asset: str, date_str: str, files_map: Dict[str, str]) -> bool:
    api_url = _get_api_url()
    if not api_url or not API_KEY:
        log("API-Konfiguration fehlt")
        return False

    try:
        with open(files_map["fullhd"], "rb") as f1, \
             open(files_map["mobile"], "rb") as f2, \
             open(files_map["thumb"], "rb") as f3:

            response = requests.post(
                api_url,
                headers={"X-API-Key": API_KEY},
                data={"date": date_str, "asset": asset},
                files={
                    "fullhd": ("fullhd.jpg", f1, "image/jpeg"),
                    "mobile": ("mobile.jpg", f2, "image/jpeg"),
                    "thumb": ("thumb.jpg", f3, "image/jpeg"),
                },
                timeout=(HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT),
                verify=HTTP_VERIFY_SSL,
            )

        try:
            payload = response.json()
        except Exception:
            log(f"Ungueltige API-Antwort fuer {asset}: HTTP {response.status_code}")
            return False

        if response.ok and payload.get("ok") is True:
            log(f"Upload erfolgreich: {asset}")
            return True

        log(f"Upload fehlgeschlagen: {asset} -> {payload}")
        return False

    except Exception as e:
        log(f"HTTPS-Upload fehlgeschlagen ({asset}): {e}")
        return False


def _post_video(asset: str, date_str: str, video_path: str, thumb_path: str) -> bool:
    api_url = _get_api_url()
    if not api_url or not API_KEY:
        log("API-Konfiguration fehlt")
        return False

    video_ext = os.path.splitext(video_path)[1].lower()
    video_mime = "video/mp4" if video_ext == ".mp4" else "video/webm"

    try:
        with open(video_path, "rb") as fv, open(thumb_path, "rb") as ft:
            response = requests.post(
                api_url,
                headers={"X-API-Key": API_KEY},
                data={"date": date_str, "asset": asset},
                files={
                    "file": (os.path.basename(video_path), fv, video_mime),
                    "thumb": ("thumb.jpg", ft, "image/jpeg"),
                },
                timeout=(HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT),
                verify=HTTP_VERIFY_SSL,
            )

        try:
            payload = response.json()
        except Exception:
            log(f"Ungueltige API-Antwort fuer {asset}: HTTP {response.status_code}")
            return False

        if response.ok and payload.get("ok") is True:
            log(f"Upload erfolgreich: {asset}")
            return True

        log(f"Upload fehlgeschlagen: {asset} -> {payload}")
        return False

    except Exception as e:
        log(f"HTTPS-Upload fehlgeschlagen ({asset}): {e}")
        return False


# ---------------------------------------------------------------------
# Datei-Suche
# ---------------------------------------------------------------------
def _collect_assets(date_str: str) -> List[Tuple[str, str]]:
    images_base = os.path.join(config.ALLSKY_PATH, config.IMAGE_BASE_PATH)
    indi_flag = _truthy(getattr(config, "INDI", 0))

    found: List[Tuple[str, str]] = []

    if not indi_flag:
        mp4_path = os.path.join(images_base, date_str, f"allsky-{date_str}.mp4")
        webm_path = os.path.join(images_base, date_str, f"allsky-{date_str}.webm")
        video = mp4_path if os.path.isfile(mp4_path) else (webm_path if os.path.isfile(webm_path) else None)

        keo_jpg = os.path.join(images_base, date_str, "keogram", f"keogram-{date_str}.jpg")
        keo_png = os.path.join(images_base, date_str, "keogram", f"keogram-{date_str}.png")
        st_jpg  = os.path.join(images_base, date_str, "startrails", f"startrails-{date_str}.jpg")
        st_png  = os.path.join(images_base, date_str, "startrails", f"startrails-{date_str}.png")

        keo = _choose_newest_existing(keo_jpg, keo_png)
        st  = _choose_newest_existing(st_jpg, st_png)

        if keo:
            found.append(("keogram", keo))
        if st:
            found.append(("startrail", st))
        if video:
            found.append(("video", video))

        return found

    cam_id = getattr(config, "CAMERAID", None)
    if not cam_id:
        log("INDI ist aktiv, aber config.CAMERAID ist nicht gesetzt.")
        return found

    indi_cam_dir = os.path.join(images_base, cam_id)
    if not os.path.isdir(indi_cam_dir):
        log(f"INDI Kameraordner nicht gefunden: {indi_cam_dir}")
        return found

    log(f"Verwende INDI Kameraordner (aus config.CAMERAID): {indi_cam_dir}")

    date_dir = os.path.join(indi_cam_dir, "timelapse", date_str)

    keo = _latest_multi([
        os.path.join(date_dir, f"allsky-keogram_*_{date_str}_night_*.jpg"),
        os.path.join(date_dir, f"allsky-keogram_*_{date_str}_night_*.png"),
    ])
    st = _latest_multi([
        os.path.join(date_dir, f"allsky-startrail_*_{date_str}_night_*.jpg"),
        os.path.join(date_dir, f"allsky-startrail_*_{date_str}_night_*.png"),
    ])
    tl = _latest_multi([
        os.path.join(date_dir, f"allsky-timelapse_*_{date_str}_night_*.mp4"),
        os.path.join(date_dir, f"allsky-timelapse_*_{date_str}_night_*.webm"),
    ])

    log(
        f"Gefunden: keogram={os.path.basename(keo) if keo else '-'}, "
        f"startrail={os.path.basename(st) if st else '-'}, "
        f"timelapse={os.path.basename(tl) if tl else '-'}"
    )

    if keo:
        found.append(("keogram", keo))
    if st:
        found.append(("startrail", st))
    if tl:
        found.append(("video", tl))

    return found


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _scale_filter(w):
    return f"scale='if(gt(iw,{w}),{w},iw)':-2"

# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
def upload_manual_batch(date_str: str) -> bool:
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
    except ValueError:
        log(f"Ungueltiges Datum: {date_str} (erwartet: JJJJMMTT)")
        return False

    date_str = dt.strftime("%Y%m%d")
    log(f"Starte MANUELLEN HTTPS-Upload fuer {date_str}")

    if not _ffmpeg_exists():
        log("ffmpeg wurde nicht gefunden.")
        return False

    assets = _collect_assets(date_str)
    if not assets:
        log("Keine unterstuetzten Assets gefunden.")
        return False

    batch_ok = True

    for asset, local_path in assets:
        log(f"Pruefe Datei: {local_path}")

        if not local_path or not _file_available(local_path):
            log(f"Datei fehlt oder ist leer, uebersprungen: {local_path}")
            batch_ok = False
            continue

        tmp_dir = None
        try:
            tmp_dir = tempfile.mkdtemp(prefix=f"manual_upload_{asset}_")

            if asset in ("keogram", "startrail"):
                files_map = _create_three_variants(local_path, tmp_dir, asset)
                ok = _post_triple_jpg(asset, date_str, files_map)

            elif asset == "video":
                reduced_video, thumb_jpg = _prepare_video_and_thumb(local_path, tmp_dir)
                ok = _post_video(asset, date_str, reduced_video, thumb_jpg)

            else:
                log(f"Nicht unterstuetztes Asset im manuellen Upload: {asset}")
                ok = False

            if not ok:
                batch_ok = False

        except Exception as e:
            log(f"Fehler bei {asset}: {e}")
            batch_ok = False

        finally:
            if tmp_dir and os.path.isdir(tmp_dir):
                try:
                    for name in os.listdir(tmp_dir):
                        try:
                            os.remove(os.path.join(tmp_dir, name))
                        except Exception:
                            pass
                    os.rmdir(tmp_dir)
                except Exception:
                    pass

    log("Manueller HTTPS-Upload abgeschlossen.")
    return batch_ok