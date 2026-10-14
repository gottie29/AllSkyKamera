#!/usr/bin/env python3
"""AllSkyKamera API upload for TJ / INDI, with optional TJ journal metadata.

Does not change TJ-Allsky. Journal-to-live-image association is a *heuristic*;
scientific consumers MUST inspect metadata.match_status, and must not treat
it as an independently verified exposure timestamp.
"""
import os
import time
import random
import tempfile
import base64
import subprocess
import shutil
import re
import json
from datetime import datetime, timezone
from typing import Optional

import requests
from askutils import config

try:
    from askutils.utils import influx_writer
except Exception:
    influx_writer = None

try:
    from askutils.ASKsecret import API_KEY
except Exception:
    API_KEY = None

_DEFAULT_ENC_IMAGE_UPLOAD_API_URL = (
    "aHR0cHM6Ly9hbGxza3lrYW1lcmEuc3BhY2UvYXBpL3YxL2ltYWdlX3VwbG9hZC5waHA="
)
HTTP_CONNECT_TIMEOUT = 20
HTTP_READ_TIMEOUT = 120
HTTP_VERIFY_SSL = True
FULLHD_WIDTH = 1920
MOBILE_WIDTH = 960
THUMB_WIDTH = 480
JPEG_QSCALE = 2

# Journal correlation is deliberately conservative. A match is marked
# provisional, NOT as a proven identification of the exposure.
TJ_JOURNAL_WINDOW_MINUTES = 15
TJ_MAX_SAVE_MTIME_DELTA_SECONDS = 25.0


def _log_upload_status_to_influx(value: int) -> None:
    try:
        if influx_writer is None:
            return
        kamera_id = getattr(config, "KAMERA_ID", None) or getattr(config, "KAMERA", None)
        if kamera_id:
            influx_writer.log_metric("uploadstatus", {"imageupload": float(value)},
                                     tags={"host": "host1", "kamera": str(kamera_id)})
    except Exception:
        pass


def log(msg: str) -> None:
    print(msg, flush=True)


def _get_api_url() -> str:
    return base64.b64decode(_DEFAULT_ENC_IMAGE_UPLOAD_API_URL).decode().strip()


def _choose_newest_existing(*candidates: str) -> Optional[str]:
    files = [p for p in candidates if p and os.path.isfile(p)]
    return max(files, key=lambda p: os.path.getmtime(p)) if files else None


def _apply_upload_jitter() -> None:
    max_s = getattr(config, "IMAGE_UPLOAD_JITTER_MAX_SECONDS", 30)
    try:
        max_s = int(max_s)
    except Exception:
        max_s = 30
    if max_s > 0:
        delay = random.randint(0, max_s)
        if delay:
            log(f"Jitter: warte {delay}s vor API-Upload ...")
            time.sleep(delay)


def _is_file_too_old(path: str) -> bool:
    max_age = getattr(config, "IMAGE_UPLOAD_MAX_AGE_SECONDS", 300)
    try:
        max_age = int(max_age)
    except Exception:
        max_age = 300
    if max_age <= 0:
        return False
    try:
        return time.time() - os.path.getmtime(path) > max_age
    except Exception:
        return False


def _get_default_image_path() -> Optional[str]:
    if not getattr(config, "INDI", 0):
        return _choose_newest_existing(
            os.path.join(config.ALLSKY_PATH, config.IMAGE_PATH, "image.jpg"),
            os.path.join(config.ALLSKY_PATH, config.IMAGE_PATH, "image.png"))
    return _choose_newest_existing(
        os.path.join(config.ALLSKY_PATH, config.IMAGE_BASE_PATH, "latest.jpg"),
        os.path.join(config.ALLSKY_PATH, config.IMAGE_BASE_PATH, "latest.png"))


def _snapshot_image(src: str, temp_dir: str) -> tuple:
    """Read a stable snapshot, preserving source mtime for journal correlation.

    Recheck inode/mtime/size after copy. If source changes during copy, fail
    safely rather than uploading an uncertain image/metadata pair.
    """
    suffix = os.path.splitext(src)[1].lower()
    if suffix not in (".jpg", ".jpeg", ".png"):
        raise ValueError(f"Nicht unterstuetztes Quellformat: {suffix}")
    dst = os.path.join(temp_dir, "snapshot" + suffix)
    with open(src, "rb") as inp:
        before = os.fstat(inp.fileno())
        if not before.st_size:
            raise ValueError("Quellbild ist leer")
        with open(dst, "wb") as out:
            shutil.copyfileobj(inp, out, length=1024 * 1024)
        after = os.fstat(inp.fileno())
    try:
        path_after = os.stat(src)
    except OSError as exc:
        raise RuntimeError("Quellbild waehrend des Lesens entfernt") from exc
    attrs = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
    if (any(getattr(before, a) != getattr(after, a) for a in attrs)
            or any(getattr(after, a) != getattr(path_after, a) for a in attrs)
            or os.path.getsize(dst) != after.st_size):
        raise RuntimeError("Quellbild waehrend des Snapshots veraendert; Upload abgebrochen")
    return dst, before.st_mtime


def _run_ffmpeg_create_jpg(src: str, dst: str, width: int) -> None:
    subprocess.check_call([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src,
        "-frames:v", "1",
        "-vf", f"scale='if(gt(iw,{width}),{width},iw)':-2",
        "-q:v", str(JPEG_QSCALE), "-pix_fmt", "yuvj420p", dst])


def _create_variants(src: str, tmp_dir: str) -> dict:
    variants = {"fullhd": os.path.join(tmp_dir, "fullhd.jpg"),
                "mobile": os.path.join(tmp_dir, "mobile.jpg"),
                "thumb": os.path.join(tmp_dir, "thumb.jpg")}
    for name, width in (("fullhd", FULLHD_WIDTH),
                        ("mobile", MOBILE_WIDTH), ("thumb", THUMB_WIDTH)):
        _run_ffmpeg_create_jpg(src, variants[name], width)
    return variants


def _build_payload_meta() -> dict:
    kamera_id = getattr(config, "KAMERA_ID", None) or getattr(config, "KAMERA", None) or ""
    return {"kamera": str(kamera_id), "asset": "image"}


_SAVE_RE = re.compile(r"Saving\s+(DAY|NIGHT)\s+image\s+'image-(\d{14})\.[^']+'", re.I)
_GOT_RE = re.compile(r"GOT IMAGE:.*?shutter_us:\s*([0-9]+(?:[.,][0-9]+)?)\s*(sec|ms|us|µs).*?gain:\s*([0-9]+(?:[.,][0-9]+)?)", re.I)
_JOURNAL_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s+.*?:\s*(.*)$")


def _parse_decimal(text: str) -> float:
    """TJ logs often use German decimal commas."""
    if "," in text and "." not in text:
        return float(text.replace(",", "."))
    return float(text)


def _journal_metadata(source_mtime: float) -> Optional[dict]:
    """Find a *provisional* journal correlation for the snapshot image.

    The source JPEG itself does not carry a provenance identifier; a mtime
    association cannot prove that its pixels belong to the journal record.
    """
    if getattr(config, "INDI", 0):
        return None
    try:
        result = subprocess.run(
            ["journalctl", "-u", "allsky", "--since", f"{TJ_JOURNAL_WINDOW_MINUTES} minutes ago",
             "--no-pager", "--output=short-unix"],
            capture_output=True, text=True, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None

    matches = []
    last_got = None
    for line in result.stdout.splitlines():
        item = _JOURNAL_RE.match(line)
        if not item:
            continue
        log_epoch, message = float(item.group(1)), item.group(2)
        got = _GOT_RE.search(message)
        if got:
            try:
                v = _parse_decimal(got.group(1))
                unit = got.group(2).lower()
                exposure_us = int(round(v * {"sec": 1_000_000, "ms": 1000,
                                             "us": 1, "µs": 1}[unit]))
                gain = _parse_decimal(got.group(3))
                last_got = (log_epoch, exposure_us, gain)
            except (ValueError, KeyError):
                last_got = None
            continue
        saved = _SAVE_RE.search(message)
        if not saved:
            continue
        # GOT IMAGE belongs to the same capture only when it preceded the
        # saving line closely. A missing value is represented as null.
        exposure_us, gain = None, None
        if last_got is not None and 0 <= log_epoch - last_got[0] <= 10:
            exposure_us, gain = last_got[1], last_got[2]
        last_got = None
        delta = source_mtime - log_epoch
        if abs(delta) <= TJ_MAX_SAVE_MTIME_DELTA_SECONDS:
            matches.append((abs(delta), saved.group(2), log_epoch,
                            exposure_us, gain, saved.group(1)))

    if len(matches) != 1:
        return None
    _, filename_time, save_epoch, exposure_us, gain, day_or_night = matches[0]

    # Convert filename's local time using configured local timezone, if given.
    # Do not silently assume Europe/Berlin for network cameras elsewhere.
    zone_name = None
    system_time = getattr(config, "SYSTEM_TIME", None)
    if isinstance(system_time, dict):
        zone_name = system_time.get("timezone_name")
    if not zone_name:
        try:
            with open("/etc/timezone", encoding="utf-8") as fh:
                zone_name = fh.read().strip()
        except OSError:
            pass
    if not zone_name:
        return None
    try:
        from zoneinfo import ZoneInfo
        local_dt = datetime.strptime(filename_time, "%Y%m%d%H%M%S").replace(tzinfo=ZoneInfo(zone_name))
        start_utc = local_dt.astimezone(timezone.utc)
    except (ImportError, ValueError, KeyError):
        return None
    # Ensure timezone and journal wall-clock information agree (within processing overhead).
    if not 0 <= save_epoch - start_utc.timestamp() <= 300:
        return None

    result = {
        "schema_version": 1,
        "source_interface": "tj-allsky",
        "timestamp_source": "tj_journal_filename_and_file_mtime",
        "match_status": "provisional_unverified",
        "capture_time_semantics": "tj_reported_exposure_start",
        "captured_at_utc": start_utc.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "capture_local_timezone": zone_name,
        "tj_original_filename": f"image-{filename_time}.jpg",
        "exposure_us": exposure_us,
        "gain": gain,
        "day_or_night": day_or_night.upper(),
    }
    if exposure_us is not None and exposure_us >= 0:
        midpoint = datetime.fromtimestamp(start_utc.timestamp() + exposure_us / 2_000_000,
                                          timezone.utc)
        result["capture_midpoint_utc"] = midpoint.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return result


def _upload_variants_to_api(variants: dict, capture_meta: Optional[dict] = None) -> bool:
    url = _get_api_url()
    if not API_KEY:
        log("API_KEY fehlt.")
        return False
    headers = {"X-API-Key": API_KEY}
    try:
        with open(variants["fullhd"], "rb") as fh_fullhd, \
             open(variants["mobile"], "rb") as fh_mobile, \
             open(variants["thumb"], "rb") as fh_thumb:
            files = {
                "fullhd": ("fullhd.jpg", fh_fullhd, "image/jpeg"),
                "mobile": ("mobile.jpg", fh_mobile, "image/jpeg"),
                "thumb": ("thumb.jpg", fh_thumb, "image/jpeg"),
            }
            data = _build_payload_meta()
            if capture_meta is not None:
                # Additional optional form field; older APIs normally ignore
                # it. Server-side storage requires separate API implementation.
                data["capture_metadata"] = json.dumps(capture_meta, separators=(",", ":"))
            response = requests.post(url, headers=headers, data=data, files=files,
                                     timeout=(HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT),
                                     verify=HTTP_VERIFY_SSL)
    except requests.RequestException as exc:
        log(f"API-Upload fehlgeschlagen (Request): {exc}")
        return False
    except Exception as exc:
        log(f"API-Upload fehlgeschlagen (Prepare): {exc}")
        return False
    if response.status_code != 200:
        body = (response.text or "")[:1000].replace("\n", " ").replace("\r", " ")
        log(f"API-Upload HTTP-Fehler {response.status_code}: {body}")
        return False
    try:
        result = response.json()
    except Exception:
        log(f"API antwortet nicht mit JSON: {(response.text or '')[:500]}")
        return False
    if result.get("ok") is not True:
        log(f"API meldet Fehler: {str(result)[:1000]}")
        return False
    log("API-Upload erfolgreich.")
    return True


def upload_image_tj_api(image_path: Optional[str] = None) -> bool:
    if image_path is None:
        image_path = _get_default_image_path()
    if not image_path or not os.path.isfile(image_path):
        log(f"Datei nicht gefunden: {image_path}")
        _log_upload_status_to_influx(3)
        return False
    if _is_file_too_old(image_path):
        log(f"Datei zu alt, Upload wird uebersprungen: {image_path}")
        _log_upload_status_to_influx(4)
        return False

    tmp_dir = None
    try:
        # Snapshot BEFORE the upload jitter: frame and its mtime must refer
        # to the same immutable bytes, independently of TJ's next capture.
        tmp_dir = tempfile.mkdtemp(prefix="askutils_image_api_")
        snapshot, original_mtime = _snapshot_image(image_path, tmp_dir)
        meta = _journal_metadata(original_mtime)
        if meta:
            log("TJ-Aufnahmemetadaten gefunden (nur vorlaeufiger Journal-Abgleich).")
        else:
            log("Keine eindeutigen TJ-Aufnahmemetadaten: Upload ohne Aufnahmezeit.")
        _apply_upload_jitter()
        variants = _create_variants(snapshot, tmp_dir)
        ok = _upload_variants_to_api(variants, meta)
        _log_upload_status_to_influx(1 if ok else 2)
        return ok
    except Exception as exc:
        log(f"API-Upload fehlgeschlagen: {exc}")
        _log_upload_status_to_influx(2)
        return False
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)

