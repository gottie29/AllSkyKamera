# askutils/uploader/image_upload_api.py

import base64
import hashlib
import json
import os
import subprocess
import tempfile
import time
from contextlib import contextmanager
from typing import Dict, Optional, Tuple

import requests

from askutils import config

# Secret Key von Kamera
try:
    from askutils.ASKsecret import API_KEY
except Exception:
    API_KEY = None

# verschlüsselte Default Upload API URL
_DEFAULT_ENC_UPLOAD_API_URL = "aHR0cHM6Ly9hbGxza3lrYW1lcmEuc3BhY2UvYXBpL3YxL2ltYWdlX3VwbG9hZC5waHA="

# Influx Writer
try:
    from askutils.utils import influx_writer
except Exception:
    influx_writer = None


# ---------------------------------------------------------
# Feste Zielbreiten
# ---------------------------------------------------------
FULLHD_WIDTH = 1920
MOBILE_WIDTH = 960
THUMB_WIDTH = 480

# ffmpeg JPEG Qualität:
# kleiner = bessere Qualität
# 2 ist praktisch "maximal sinnvoll"
JPEG_QSCALE = 2


# ---------------------------------------------------------
# Status-/Fehlercodes
# ---------------------------------------------------------
STATUS_OK = 1
STATUS_FAILED = 2
STATUS_SOURCE_NOT_FOUND = 3
STATUS_SOURCE_TOO_OLD = 4
STATUS_FFMPEG_FAILED = 5
STATUS_API_CONFIG_MISSING = 6
STATUS_LOCK_ACTIVE = 7
STATUS_INVALID_API_RESPONSE = 8
STATUS_SKIPPED_UNCHANGED = 9


# ---------------------------------------------------------
# Influx Logging
# ---------------------------------------------------------
def _log_upload_status_to_influx(status_value: int, error_code: str = "") -> None:
    try:
        if influx_writer is None:
            return

        kamera_id = getattr(config, "KAMERA_ID", None) or getattr(config, "KAMERA", None)
        if not kamera_id:
            return

        tags = {"host": "host1", "kamera": str(kamera_id)}
        if error_code:
            tags["error_code"] = str(error_code)

        influx_writer.log_metric(
            "uploadstatus",
            {
                "imageupload_api": float(status_value),
                "imageupload_api_code": float(status_value),
            },
            tags=tags
        )

    except Exception:
        pass


# ---------------------------------------------------------
# API URL
# ---------------------------------------------------------
def _get_api_url() -> Optional[str]:
    try:
        url = base64.b64decode(_DEFAULT_ENC_UPLOAD_API_URL).decode().strip()
    except Exception:
        return None

    if not url.startswith("https://"):
        raise RuntimeError("Upload API must use HTTPS")

    return url


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def _choose_newest_existing(*candidates: str) -> Optional[str]:
    files = [p for p in candidates if p and os.path.isfile(p)]
    if not files:
        return None
    return max(files, key=lambda p: os.path.getmtime(p))


def _resolve_source_image(image_path: Optional[str] = None) -> Optional[str]:
    if image_path:
        return image_path if os.path.isfile(image_path) else None

    indi_flag = getattr(config, "INDI", 0)

    if not indi_flag:
        jpg = os.path.join(config.ALLSKY_PATH, config.IMAGE_PATH, "image.jpg")
        png = os.path.join(config.ALLSKY_PATH, config.IMAGE_PATH, "image.png")
        return _choose_newest_existing(jpg, png)

    jpg = os.path.join(config.ALLSKY_PATH, config.IMAGE_BASE_PATH, "latest.jpg")
    png = os.path.join(config.ALLSKY_PATH, config.IMAGE_BASE_PATH, "latest.png")
    return _choose_newest_existing(jpg, png)


def _is_file_too_old(path: str) -> bool:
    max_age = getattr(config, "IMAGE_UPLOAD_API_MAX_AGE_SECONDS", 300)

    try:
        max_age = int(max_age)
    except Exception:
        max_age = 300

    if max_age <= 0:
        return False

    try:
        mtime = os.path.getmtime(path)
    except Exception:
        return False

    age = time.time() - mtime
    return age > max_age


def _camera_id() -> str:
    return str(getattr(config, "KAMERA_ID", None) or getattr(config, "KAMERA", "UNKNOWN"))


def _get_state_dir() -> str:
    return os.path.join(config.ALLSKY_PATH, "tmp")


def _get_state_file() -> str:
    return os.path.join(_get_state_dir(), "image_upload_api_state.json")


def _sha256_of_file(path: str, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _load_state() -> dict:
    state_file = _get_state_file()
    if not os.path.isfile(state_file):
        return {}

    try:
        with open(state_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    os.makedirs(_get_state_dir(), exist_ok=True)
    state_file = _get_state_file()
    tmp_file = state_file + ".tmp"

    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    os.replace(tmp_file, state_file)


def _is_source_unchanged(source_path: str) -> Tuple[bool, str]:
    current_hash = _sha256_of_file(source_path)
    state = _load_state()
    last_hash = str(state.get("last_source_sha256", "")).strip()
    return current_hash == last_hash and last_hash != "", current_hash


def _mark_successful_upload(source_path: str, source_hash: str) -> None:
    state = _load_state()
    state["last_source_sha256"] = source_hash
    state["last_source_path"] = source_path
    state["last_success_ts"] = int(time.time())
    try:
        state["last_source_mtime"] = int(os.path.getmtime(source_path))
    except Exception:
        state["last_source_mtime"] = None
    _save_state(state)


# ---------------------------------------------------------
# deterministic jitter
# ---------------------------------------------------------
def _apply_deterministic_jitter() -> None:
    max_s = getattr(config, "IMAGE_UPLOAD_API_JITTER_MAX_SECONDS", 30)

    try:
        max_s = int(max_s)
    except Exception:
        max_s = 30

    if max_s <= 0:
        return

    cam = _camera_id().encode("utf-8")
    digest = hashlib.sha1(cam).hexdigest()
    delay = int(digest[:8], 16) % (max_s + 1)

    if delay > 0:
        print(f"Deterministic jitter: warte {delay}s vor Bildaufbereitung/Upload ...")
        time.sleep(delay)


# ---------------------------------------------------------
# ffmpeg
# ---------------------------------------------------------
def _build_scale_filter(max_width: int) -> str:
    # Nur verkleinern, niemals vergroessern.
    # Hoehe bleibt proportional; -2 erzwingt gerade Zielhoehe.
    return f"scale='if(gt(iw,{max_width}),{max_width},iw)':-2"


def _create_derivative(src: str, dst: str, width: int) -> None:
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
        raise RuntimeError(f"ffmpeg_failed: {stderr}")


def _create_all_derivatives(src: str, tmp_dir: str) -> Dict[str, str]:
    fullhd = os.path.join(tmp_dir, "image_fullhd.jpg")
    mobile = os.path.join(tmp_dir, "image_mobile.jpg")
    thumb = os.path.join(tmp_dir, "image_thumb.jpg")

    _create_derivative(src, fullhd, FULLHD_WIDTH)
    _create_derivative(src, mobile, MOBILE_WIDTH)
    _create_derivative(src, thumb, THUMB_WIDTH)

    return {
        "fullhd": fullhd,
        "mobile": mobile,
        "thumb": thumb
    }


# ---------------------------------------------------------
# Lockfile
# ---------------------------------------------------------
@contextmanager
def _file_lock(lock_path: str):
    import fcntl

    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o664)

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise RuntimeError("upload_lock_active")

    try:
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode("utf-8"))
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            os.close(fd)
        except Exception:
            pass


# ---------------------------------------------------------
# Upload
# ---------------------------------------------------------
def _post_files(files_map: Dict[str, str]) -> bool:
    api_url = _get_api_url()

    if not api_url or not API_KEY:
        print("API Konfiguration fehlt")
        _log_upload_status_to_influx(STATUS_API_CONFIG_MISSING, "api_config_missing")
        return False

    headers = {
        "X-API-Key": API_KEY
    }

    try:
        with open(files_map["fullhd"], "rb") as f1, \
             open(files_map["mobile"], "rb") as f2, \
             open(files_map["thumb"], "rb") as f3:

            files = {
                "fullhd": ("image_fullhd.jpg", f1, "image/jpeg"),
                "mobile": ("image_mobile.jpg", f2, "image/jpeg"),
                "thumb": ("image_thumb.jpg", f3, "image/jpeg"),
            }

            response = requests.post(
                api_url,
                headers=headers,
                files=files,
                timeout=(10, 30)
            )

        if response.status_code == 429:
            print("Rate limit erreicht")
            _log_upload_status_to_influx(STATUS_FAILED, "api_rate_limit")
            return False

        try:
            payload = response.json()
        except Exception:
            print(f"Ungültige API-Antwort: HTTP {response.status_code}")
            _log_upload_status_to_influx(STATUS_INVALID_API_RESPONSE, "invalid_api_response")
            return False

        if response.ok and payload.get("ok"):
            print("Upload erfolgreich")
            _log_upload_status_to_influx(STATUS_OK, "ok")
            return True

        error_text = str(payload.get("error", "api_error")).strip()[:80]
        print("Upload Fehler:", payload)
        _log_upload_status_to_influx(STATUS_FAILED, error_text or "api_error")
        return False

    except requests.RequestException as e:
        print("Upload Exception:", e)
        _log_upload_status_to_influx(STATUS_FAILED, "request_exception")
        return False

    except Exception as e:
        print("Upload Exception:", e)
        _log_upload_status_to_influx(STATUS_FAILED, "upload_exception")
        return False


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------
def upload_image_api(image_path: Optional[str] = None) -> bool:
    lock_path = os.path.join(config.ALLSKY_PATH, "tmp", "image_upload_api.lock")

    try:
        with _file_lock(lock_path):
            source = _resolve_source_image(image_path)

            if not source:
                print("Source image not found")
                _log_upload_status_to_influx(STATUS_SOURCE_NOT_FOUND, "source_not_found")
                return False

            if _is_file_too_old(source):
                print("Source image too old")
                _log_upload_status_to_influx(STATUS_SOURCE_TOO_OLD, "source_too_old")
                return False

            unchanged, source_hash = _is_source_unchanged(source)
            if unchanged:
                print("Upload uebersprungen: Bild unveraendert")
                _log_upload_status_to_influx(STATUS_SKIPPED_UNCHANGED, "skipped_unchanged")
                return False

            _apply_deterministic_jitter()

            with tempfile.TemporaryDirectory(prefix="askutils_upload_") as tmp:
                try:
                    files = _create_all_derivatives(source, tmp)
                except Exception as e:
                    print("ffmpeg error:", e)
                    _log_upload_status_to_influx(STATUS_FFMPEG_FAILED, "ffmpeg_failed")
                    return False

                ok = _post_files(files)

                if ok:
                    _mark_successful_upload(source, source_hash)

                return ok

    except RuntimeError as e:
        if str(e) == "upload_lock_active":
            print("Upload skipped, lock active")
            _log_upload_status_to_influx(STATUS_LOCK_ACTIVE, "lock_active")
            return False

        print("Upload runtime error:", e)
        _log_upload_status_to_influx(STATUS_FAILED, "runtime_error")
        return False

    except Exception as e:
        print("Upload error:", e)
        _log_upload_status_to_influx(STATUS_FAILED, "unexpected_error")
        return False