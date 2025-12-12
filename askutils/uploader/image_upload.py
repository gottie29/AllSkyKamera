# askutils/uploader/image_upload.py

import os
import ftplib
from askutils import config

def upload_image(image_path: str = None) -> bool:
    """
    Laedt eine einzelne Bilddatei per FTP hoch.
    - Thomas Jaquin:   .../<IMAGE_PATH>/image.jpg  -> als 'image.jpg' hochladen
    - INDI:            .../<ALLSKY_PATH>/latest.jpg -> als **'image.jpg'** hochladen
      (atomar: Upload als .tmp und serverseitiges Rename)
    """

    # --- Lokaler Pfad bestimmen ---
    indi_flag = getattr(config, "INDI", 0)

    # Alles, was "falsey" ist (None, 0, "", False, "0") => Jaquin-Standard
    if not indi_flag:
        # Jaquin (Standard)
        if image_path is None:
            image_path = os.path.join(config.ALLSKY_PATH, config.IMAGE_PATH, "image.jpg")
    else:
        # INDI
        if image_path is None:
            image_path = os.path.join(config.ALLSKY_PATH, config.IMAGE_BASE_PATH, "latest.jpg")

    if not os.path.isfile(image_path):
        print(f"Datei nicht gefunden: {image_path}")
        return False

    # --- Ziel-Dateiname auf dem Server ---
    # Bei INDI immer als 'image.jpg' hochladen, sonst Dateiname beibehalten.
    if config.INDI is None:
        remote_name = os.path.basename(image_path)  # i.d.R. 'image.jpg'
    else:
        remote_name = "image.jpg"                   # latest.jpg -> image.jpg auf dem Server

    tmp_name = remote_name + ".tmp"

    try:
        with ftplib.FTP(config.FTP_SERVER) as ftp:
            ftp.login(config.FTP_USER, config.FTP_PASS)
            ftp.cwd(config.FTP_REMOTE_DIR)

            # Atomarer Upload: erst .tmp, dann Rename auf finalen Namen
            with open(image_path, "rb") as f:
                ftp.storbinary(f"STOR {tmp_name}", f)
            try:
                # Falls bereits eine alte image.jpg existiert, wird sie durch RNTO ueberschrieben
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
