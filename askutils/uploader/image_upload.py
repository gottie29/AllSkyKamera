# askutils/uploader/image_upload.py

import os
import ftplib
import tempfile
import time
import random
from askutils import config


def _choose_newest_existing(*candidates: str) -> str | None:
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

    # Qualität/Optimierung: guter Kompromiss
    img.save(tmp_path, format="JPEG", quality=90, optimize=True)
    return tmp_path


def _apply_upload_jitter() -> None:
    """
    Verteilt Lastspitzen: wartet zufällig 0..N Sekunden vor dem FTP-Login.
    Wichtig für den 2-Minuten-Upload: Default ist bewusst klein (30s),
    damit keine Cron-Überlappung entsteht.
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


def upload_image(image_path: str = None) -> bool:
    """
    Lädt eine einzelne Bilddatei per FTP hoch.

    Verhalten:
    - Wenn lokal PNG verwendet wird, wird es TEMP zu JPG konvertiert,
      dann wird nur das JPG hochgeladen und danach wieder gelöscht.
    - Wenn lokal sowohl JPG als auch PNG existieren, wird immer die NEUERE Datei
      (mtime) gewählt, damit alte Reste nicht “gewinnen”.
    - Auf dem Server landet immer: image.jpg
    - Atomar: Upload als image.jpg.tmp und serverseitiges Rename.

    Pfade:
    - Jaquin: .../<IMAGE_PATH>/image.(jpg|png)
    - INDI:   .../<IMAGE_BASE_PATH>/latest.(jpg|png)
    """

    # --- Lokalen Pfad bestimmen ---
    indi_flag = getattr(config, "INDI", 0)

    if image_path is None:
        if not indi_flag:
            # Jaquin-Standard: image.jpg oder image.png (neueste gewinnt)
            jpg = os.path.join(config.ALLSKY_PATH, config.IMAGE_PATH, "image.jpg")
            png = os.path.join(config.ALLSKY_PATH, config.IMAGE_PATH, "image.png")
            image_path = _choose_newest_existing(jpg, png)
        else:
            # INDI: latest.jpg oder latest.png (neueste gewinnt)
            jpg = os.path.join(config.ALLSKY_PATH, config.IMAGE_BASE_PATH, "latest.jpg")
            png = os.path.join(config.ALLSKY_PATH, config.IMAGE_BASE_PATH, "latest.png")
            image_path = _choose_newest_existing(jpg, png)

    if not image_path or not os.path.isfile(image_path):
        print(f"Datei nicht gefunden: {image_path}")
        return False

    # --- ggf. PNG -> temporäres JPG ---
    local_upload_path = image_path
    temp_jpg_path = None

    try:
        if os.path.splitext(image_path)[1].lower() == ".png":
            temp_jpg_path = _png_to_temp_jpg(image_path)
            local_upload_path = temp_jpg_path

        # --- Ziel-Dateiname auf dem Server (immer JPG) ---
        remote_name = "image.jpg"
        tmp_name = remote_name + ".tmp"

        # --- Jitter vor FTP-Login (gegen gleichzeitige Peaks) ---
        _apply_upload_jitter()

        with ftplib.FTP(config.FTP_SERVER) as ftp:
            ftp.login(config.FTP_USER, config.FTP_PASS)
            ftp.cwd(config.FTP_REMOTE_DIR)

            # Atomarer Upload: erst .tmp, dann Rename auf finalen Namen
            with open(local_upload_path, "rb") as f:
                ftp.storbinary(f"STOR {tmp_name}", f)

            try:
                ftp.rename(tmp_name, remote_name)
            except ftplib.error_perm as e:
                # Cleanup bei Fehler
                try:
                    ftp.delete(tmp_name)
                except Exception:
                    pass
                raise e

        print(f"Upload abgeschlossen: {remote_name} -> /{config.FTP_REMOTE_DIR}")
        return True

    except Exception as e:
        print(f"FTP-Upload fehlgeschlagen: {e}")
        return False

    finally:
        # Temp-JPG nach Upload/Fehler wieder löschen
        if temp_jpg_path and os.path.isfile(temp_jpg_path):
            try:
                os.remove(temp_jpg_path)
            except Exception:
                pass
