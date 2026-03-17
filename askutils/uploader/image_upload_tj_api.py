#!/usr/bin/env python3
# askutils/uploader/image_upload_api.py

import os
import time
import random
import tempfile
import base64
import subprocess
from typing import Optional

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
# Bitte prüfen/anpassen, falls dein Server-Endpunkt anders heißt.
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
    """
    Gibt den existierenden Kandidaten mit dem neuesten mtime zurück.
    Beachtet damit Fälle wie: altes JPG + aktuelles PNG (oder umgekehrt).
    """
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
        log(f"Jitter: warte {delay}s vor API-Upload ...")
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
        # wenn wir nicht auf mtime zugreifen koennen, lieber normal weiter versuchen
        return False

    age = time.time() - mtime
    return age > max_age


def _get_default_image_path() -> Optional[str]:
    """
    Ermittelt den Standardpfad für das aktuelle Live-Bild.

    TJ / non-INDI:
      ALLSKY_PATH + IMAGE_PATH + image.jpg|image.png

    INDI:
      ALLSKY_PATH + IMAGE_BASE_PATH + latest.jpg|latest.png
    """
    indi_flag = getattr(config, "INDI", 0)

    if not indi_flag:
        jpg = os.path.join(config.ALLSKY_PATH, config.IMAGE_PATH, "image.jpg")
        png = os.path.join(config.ALLSKY_PATH, config.IMAGE_PATH, "image.png")
        return _choose_newest_existing(jpg, png)

    jpg = os.path.join(config.ALLSKY_PATH, config.IMAGE_BASE_PATH, "latest.jpg")
    png = os.path.join(config.ALLSKY_PATH, config.IMAGE_BASE_PATH, "latest.png")
    return _choose_newest_existing(jpg, png)


def _run_ffmpeg_create_jpg(src: str, dst: str, width: int) -> None:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-i", src,
        "-frames:v", "1",
        "-vf", f"scale='if(gt(iw,{width}),{width},iw)':-2",
        "-q:v", str(JPEG_QSCALE),
        "-pix_fmt", "yuvj420p",
        dst,
    ]
    subprocess.check_call(cmd)


def _create_variants(src: str, tmp_dir: str) -> dict:
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
def _upload_variants_to_api(variants: dict) -> bool:
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
        log(f"API-Upload fehlgeschlagen (Request): {e}")
        return False
    except Exception as e:
        log(f"API-Upload fehlgeschlagen (Prepare): {e}")
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


# -----------------------------
# Main upload
# -----------------------------
def upload_image_tj_api(image_path: Optional[str] = None) -> bool:
    """
    Lädt eine einzelne Live-Bilddatei per API hoch.

    Statuscodes (Influx):
    - 1: Upload erfolgreich
    - 2: Upload abgebrochen/fehlgeschlagen
    - 3: Datei nicht gefunden
    - 4: Datei zu alt (Upload bewusst übersprungen)
    """

    # --- Lokalen Pfad bestimmen ---
    if image_path is None:
        image_path = _get_default_image_path()

    if not image_path or not os.path.isfile(image_path):
        log(f"Datei nicht gefunden: {image_path}")
        _log_upload_status_to_influx(3)
        return False

    # --- Age-Check (zu alt?) ---
    if _is_file_too_old(image_path):
        log(f"Datei zu alt, Upload wird uebersprungen: {image_path}")
        _log_upload_status_to_influx(4)
        return False

    tmp_dir = None

    try:
        _apply_upload_jitter()

        tmp_dir = tempfile.mkdtemp(prefix="askutils_image_api_")
        variants = _create_variants(image_path, tmp_dir)

        ok = _upload_variants_to_api(variants)
        if ok:
            _log_upload_status_to_influx(1)
            return True

        _log_upload_status_to_influx(2)
        return False

    except Exception as e:
        log(f"API-Upload fehlgeschlagen: {e}")
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