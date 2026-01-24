# askutils/uploader/image_upload.py

import os
import ftplib
import tempfile
import time
import random
from typing import Optional
from askutils import config

# Influx Writer (wie bei raspi_status)
try:
    from askutils.utils import influx_writer
except Exception:
    influx_writer = None


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
# Helpers
# -----------------------------
def _choose_newest_existing(*candidates: str) -> Optional[str]:
    """
    Gibt den existierenden Kandidaten mit dem neuesten mtime zurück.
    Beachtet damit Fälle wie: altes JPG + aktuelles PNG (oder umgekehrt).
    """
    files = [p for p in candidates if p and os.path.isfile(p)]
    if not files:
        return None
    return max(files, key=lambda p: os.path.getmtime(p))


def _png_to_temp_jpg(png_path: str) -> str:
    """
    Konvertiert PNG -> temporäres JPG (RGB), gibt Pfad der temp-Datei zurück.
    Alpha wird auf schwarz geflattet (passt gut für Allsky).
    """
    try:
        from PIL import Image
    except ImportError as e:
        raise RuntimeError(
            "Pillow ist nicht installiert. Bitte installieren mit: pip install pillow"
        ) from e

    img = Image.open(png_path)

    # PNG mit Alpha sauber auf schwarz flatten
    if img.mode in ("RGBA", "LA") or ("transparency" in getattr(img, "info", {})):
        img = img.convert("RGBA")
        bg = Image.new("RGBA", img.size, (0, 0, 0, 255))
        img = Image.alpha_composite(bg, img).convert("RGB")
    else:
        img = img.convert("RGB")

    fd, tmp_path = tempfile.mkstemp(prefix="askutils_image_", suffix=".jpg")
    os.close(fd)

    img.save(tmp_path, format="JPEG", quality=90, optimize=True)
    return tmp_path


def _apply_upload_jitter() -> None:
    """
    Verteilt Lastspitzen: wartet zufällig 0..N Sekunden vor dem FTP-Login.
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
        print(f"Jitter: warte {delay}s vor FTP-Upload ...")
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


# -----------------------------
# Main upload
# -----------------------------
def upload_image(image_path: str = None) -> bool:
    """
    Lädt eine einzelne Bilddatei per FTP hoch.

    Statuscodes (Influx):
    - 1: Upload erfolgreich
    - 2: Upload abgebrochen/fehlgeschlagen
    - 3: Datei nicht gefunden
    - 4: Datei zu alt (Upload bewusst übersprungen)
    """

    # --- Lokalen Pfad bestimmen ---
    indi_flag = getattr(config, "INDI", 0)

    if image_path is None:
        if not indi_flag:
            jpg = os.path.join(config.ALLSKY_PATH, config.IMAGE_PATH, "image.jpg")
            png = os.path.join(config.ALLSKY_PATH, config.IMAGE_PATH, "image.png")
            image_path = _choose_newest_existing(jpg, png)
        else:
            jpg = os.path.join(config.ALLSKY_PATH, config.IMAGE_BASE_PATH, "latest.jpg")
            png = os.path.join(config.ALLSKY_PATH, config.IMAGE_BASE_PATH, "latest.png")
            image_path = _choose_newest_existing(jpg, png)

    if not image_path or not os.path.isfile(image_path):
        print(f"Datei nicht gefunden: {image_path}")
        _log_upload_status_to_influx(3)
        return False

    # --- Age-Check (zu alt?) ---
    if _is_file_too_old(image_path):
        print(f"Datei zu alt, Upload wird uebersprungen: {image_path}")
        _log_upload_status_to_influx(4)
        return False

    # --- ggf. PNG -> temporäres JPG ---
    local_upload_path = image_path
    temp_jpg_path = None

    try:
        if os.path.splitext(image_path)[1].lower() == ".png":
            temp_jpg_path = _png_to_temp_jpg(image_path)
            local_upload_path = temp_jpg_path

        remote_name = "image.jpg"
        tmp_name = remote_name + ".tmp"

        _apply_upload_jitter()

        with ftplib.FTP(config.FTP_SERVER) as ftp:
            ftp.login(config.FTP_USER, config.FTP_PASS)
            ftp.cwd(config.FTP_REMOTE_DIR)

            with open(local_upload_path, "rb") as f:
                ftp.storbinary(f"STOR {tmp_name}", f)

            try:
                ftp.rename(tmp_name, remote_name)
            except ftplib.error_perm as e:
                try:
                    ftp.delete(tmp_name)
                except Exception:
                    pass
                raise e

        print(f"Upload abgeschlossen: {remote_name} -> /{config.FTP_REMOTE_DIR}")
        _log_upload_status_to_influx(1)
        return True

    except Exception as e:
        print(f"FTP-Upload fehlgeschlagen: {e}")
        _log_upload_status_to_influx(2)
        return False

    finally:
        if temp_jpg_path and os.path.isfile(temp_jpg_path):
            try:
                os.remove(temp_jpg_path)
            except Exception:
                pass
