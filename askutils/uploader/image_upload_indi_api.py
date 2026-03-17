#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# askutils/uploader/image_upload_indi_api.py

import os
import time
import random
import tempfile
import base64
import subprocess
from typing import Optional, Dict

import requests
from askutils import config

# Influx Writer (wie bei raspi_status)
try:
    from askutils.utils import influx_writer
except Exception:
    influx_writer = None

try:
    from askutils.ASKsecret import API_KEY
except Exception:
    API_KEY = None


# -----------------------------------------------------------
# API config
# -----------------------------------------------------------
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


# -----------------------------
# Influx status logging
# -----------------------------
def _log_upload_status_to_influx(value: int) -> None:
    """
    Schreibt Upload-Status in Influx:
    measurement = uploadstatus
    tag kamera = ASKxxx
    field imageupload:
      1 = upload_ok
      2 = upload_aborted_or_failed
      3 = file_not_found
      4 = file_too_old
    """
    try:
        if influx_writer is None:
            return

        kamera_id = getattr(config, "KAMERA_ID", None) or getattr(config, "KAMERA", None)
        if not kamera_id:
            return

        influx_writer.log_metric(
            "uploadstatus",
            {"imageupload": float(value)},
            tags={"host": "host1", "kamera": str(kamera_id)}
        )
    except Exception:
        # Logging darf Upload nie abbrechen
        pass


# -----------------------------
# Logging
# -----------------------------
def log(msg: str) -> None:
    print(msg, flush=True)


# -----------------------------
# Helpers
# -----------------------------
def _get_api_url() -> str:
    return base64.b64decode(_DEFAULT_ENC_IMAGE_UPLOAD_API_URL).decode().strip()


def _choose_newest_existing(*candidates: str) -> Optional[str]:
    files = [p for p in candidates if p and os.path.isfile(p)]
    if not files:
        return None
    return max(files, key=lambda p: os.path.getmtime(p))


def _apply_upload_jitter() -> None:
    """
    Verteilt Lastspitzen: wartet zufällig 0..N Sekunden vor dem Upload.
    Default bewusst klein (30s), damit keine Cron-Überlappung entsteht.
    """
    max_s = getattr(config, "IMAGE_UPLOAD_JITTER_MAX_SECONDS", 30)
    try:
        max_s = int(max_s)
    except Exception:
        max_s = 30

    if max_s <= 0:
        return

    delay = random.randint(0, max_s)
    if delay > 0:
        log("Jitter: warte %ss vor API-Upload ..." % delay)
        time.sleep(delay)


def _is_file_too_old(path: str) -> bool:
    """
    True wenn Datei zu alt ist und deshalb NICHT hochgeladen werden soll.

    Config:
      IMAGE_UPLOAD_MAX_AGE_SECONDS (Default 300)
        - <=0 deaktiviert den Check
    """
    max_age = getattr(config, "IMAGE_UPLOAD_MAX_AGE_SECONDS", 300)
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


def _is_file_stable(path: str, wait_seconds: int = 2) -> bool:
    """
    Verhindert Uploads von Dateien, die gerade noch geschrieben werden.
    """
    try:
        size1 = os.path.getsize(path)
        mtime1 = os.path.getmtime(path)
        time.sleep(wait_seconds)
        size2 = os.path.getsize(path)
        mtime2 = os.path.getmtime(path)
        return size1 == size2 and mtime1 == mtime2
    except Exception:
        return True


def _build_candidate_paths() -> list:
    """
    Sucht robust nach dem aktuellen INDI-Livebild.
    Unterstützt verschiedene mögliche Konfigurationen/Fallbacks.
    """
    candidates = []

    allsky_path = getattr(config, "ALLSKY_PATH", "") or ""
    image_base_path = getattr(config, "IMAGE_BASE_PATH", "") or ""
    image_path = getattr(config, "IMAGE_PATH", "") or ""

    def add_pair(base_dir: str, name_no_ext: str) -> None:
        if not base_dir:
            return
        candidates.append(os.path.join(base_dir, name_no_ext + ".jpg"))
        candidates.append(os.path.join(base_dir, name_no_ext + ".png"))

    # 1) INDI Standard: ALLSKY_PATH + IMAGE_BASE_PATH + latest.xxx
    if image_base_path:
        if os.path.isabs(image_base_path):
            add_pair(image_base_path, "latest")
            add_pair(image_base_path, "image")
        else:
            add_pair(os.path.join(allsky_path, image_base_path), "latest")
            add_pair(os.path.join(allsky_path, image_base_path), "image")

    # 2) Fallback: ALLSKY_PATH + IMAGE_PATH
    if image_path:
        if os.path.isabs(image_path):
            add_pair(image_path, "latest")
            add_pair(image_path, "image")
        else:
            add_pair(os.path.join(allsky_path, image_path), "latest")
            add_pair(os.path.join(allsky_path, image_path), "image")

    # 3) Weitere sinnvolle Fallbacks
    if allsky_path:
        add_pair(allsky_path, "latest")
        add_pair(allsky_path, "image")
        add_pair(os.path.join(allsky_path, "images"), "latest")
        add_pair(os.path.join(allsky_path, "images"), "image")

    # Doppelte Pfade entfernen, Reihenfolge behalten
    seen = set()
    unique = []
    for p in candidates:
        if p not in seen:
            unique.append(p)
            seen.add(p)

    return unique


def _get_default_image_path() -> Optional[str]:
    candidates = _build_candidate_paths()
    return _choose_newest_existing(*candidates)


def _run_ffmpeg_create_jpg(src: str, dst: str, width: int) -> None:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-i", src,
        "-frames:v", "1",
        "-vf", "scale='if(gt(iw,%d),%d,iw)':-2" % (width, width),
        "-q:v", str(JPEG_QSCALE),
        "-pix_fmt", "yuvj420p",
        dst,
    ]
    subprocess.check_call(cmd)


def _create_variants(src: str, tmp_dir: str) -> Dict[str, str]:
    """
    Erstellt aus JPG oder PNG drei JPG-Varianten:
    - fullhd.jpg
    - mobile.jpg
    - thumb.jpg
    """
    fullhd = os.path.join(tmp_dir, "fullhd.jpg")
    mobile = os.path.join(tmp_dir, "mobile.jpg")
    thumb = os.path.join(tmp_dir, "thumb.jpg")

    _run_ffmpeg_create_jpg(src, fullhd, FULLHD_WIDTH)
    _run_ffmpeg_create_jpg(src, mobile, MOBILE_WIDTH)
    _run_ffmpeg_create_jpg(src, thumb, THUMB_WIDTH)

    return {
        "fullhd": fullhd,
        "mobile": mobile,
        "thumb": thumb,
    }


def _build_payload_meta() -> dict:
    kamera_id = getattr(config, "KAMERA_ID", None) or getattr(config, "KAMERA", None) or ""
    return {
        "kamera": str(kamera_id),
        "asset": "image",
    }


# -----------------------------
# API upload
# -----------------------------
def _upload_variants_to_api(variants: Dict[str, str]) -> bool:
    url = _get_api_url()

    if not API_KEY:
        log("API_KEY fehlt.")
        return False

    headers = {
        "X-API-Key": API_KEY
    }

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

            response = requests.post(
                url,
                headers=headers,
                data=data,
                files=files,
                timeout=(HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT),
                verify=HTTP_VERIFY_SSL,
            )

    except requests.RequestException as e:
        log("API-Upload fehlgeschlagen (Request): %s" % e)
        return False
    except Exception as e:
        log("API-Upload fehlgeschlagen (Prepare): %s" % e)
        return False

    if response.status_code != 200:
        body = (response.text or "")[:1000].replace("\n", " ").replace("\r", " ")
        log("API-Upload HTTP-Fehler %s: %s" % (response.status_code, body))
        return False

    try:
        result = response.json()
    except Exception:
        log("API antwortet nicht mit JSON: %s" % ((response.text or "")[:500]))
        return False

    if result.get("ok") is not True:
        log("API meldet Fehler: %s" % (str(result)[:1000]))
        return False

    log("API-Upload erfolgreich.")
    return True


# -----------------------------
# Main upload
# -----------------------------
def upload_image_indi_api(image_path: Optional[str] = None) -> bool:
    """
    Lädt eine einzelne Live-Bilddatei per API hoch.

    Statuscodes (Influx):
    - 1: Upload erfolgreich
    - 2: Upload abgebrochen/fehlgeschlagen
    - 3: Datei nicht gefunden
    - 4: Datei zu alt (Upload bewusst übersprungen)
    """

    if image_path is None:
        image_path = _get_default_image_path()

    if not image_path or not os.path.isfile(image_path):
        log("Datei nicht gefunden: %s" % image_path)
        _log_upload_status_to_influx(3)
        return False

    if _is_file_too_old(image_path):
        log("Datei zu alt, Upload wird uebersprungen: %s" % image_path)
        _log_upload_status_to_influx(4)
        return False

    if not _is_file_stable(image_path, wait_seconds=2):
        log("Datei ist noch in Bearbeitung, Upload wird uebersprungen: %s" % image_path)
        _log_upload_status_to_influx(2)
        return False

    tmp_dir = None

    try:
        _apply_upload_jitter()

        tmp_dir = tempfile.mkdtemp(prefix="askutils_image_indi_api_")
        variants = _create_variants(image_path, tmp_dir)

        ok = _upload_variants_to_api(variants)
        if ok:
            _log_upload_status_to_influx(1)
            return True

        _log_upload_status_to_influx(2)
        return False

    except Exception as e:
        log("API-Upload fehlgeschlagen: %s" % e)
        _log_upload_status_to_influx(2)
        return False

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


# Rückwärtskompatibler Alias
def upload_image_api(image_path: Optional[str] = None) -> bool:
    return upload_image_indi_api(image_path)