# askutils/uploader/image_upload.py

import os
import ftplib
from askutils import config

def upload_image(image_path: str = None) -> bool:
    """
    Lädt eine einzelne Bilddatei per FTP hoch.
    Wenn kein Pfad übergeben wird, wird standardmäßig
    ALLSKY_PATH/IMAGE_PATH/image.jpg verwendet.
    """
    # Standard-Pfad aus Config
    if image_path is None:
        image_path = os.path.join(config.ALLSKY_PATH, config.IMAGE_PATH, "image.jpg")

    if not os.path.isfile(image_path):
        print(f" Datei nicht gefunden: {image_path}")
        return False

    try:
        with ftplib.FTP(config.FTP_SERVER) as ftp:
            ftp.login(config.FTP_USER, config.FTP_PASS)
            # ins Kamera-ID-Verzeichnis wechseln
            ftp.cwd(config.FTP_REMOTE_DIR)
            with open(image_path, "rb") as f:
                remote_name = os.path.basename(image_path)
                ftp.storbinary(f"STOR {remote_name}", f)
            print(f" Upload abgeschlossen: {remote_name} → /{config.FTP_REMOTE_DIR}")
        return True

    except Exception as e:
        print(f" FTP-Upload fehlgeschlagen: {e}")
        return False
