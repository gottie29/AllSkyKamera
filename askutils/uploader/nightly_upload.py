# askutils/uploader/nightly_upload.py

import os
import ftplib
from datetime import datetime, timedelta
from askutils import config

def upload_nightly_batch(date_str: str = None) -> bool:
    """
    Lädt Video, Keogram und Startrail des angegebenen Tages per FTP hoch.
    Wenn kein Datum übergeben wird, wird standardmäßig der Vortag verwendet.
    Pfade basieren auf ALLSKY_PATH und IMAGE_BASE_PATH aus der Config.
    """
    # Datum bestimmen
    if date_str is None:
        date_str = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    # Basis-Verzeichnis für Bild-Ordner
    images_base = os.path.join(config.ALLSKY_PATH, config.IMAGE_BASE_PATH)
    files = [
        (os.path.join(images_base, date_str, f"allsky-{date_str}.mp4"), config.FTP_VIDEO_DIR),
        (os.path.join(images_base, date_str, "keogram",  f"keogram-{date_str}.jpg"), config.FTP_KEOGRAM_DIR),
        (os.path.join(images_base, date_str, "startrails", f"startrails-{date_str}.jpg"), config.FTP_STARTRAIL_DIR),
    ]

    try:
        with ftplib.FTP(config.FTP_SERVER) as ftp:
            ftp.login(config.FTP_USER, config.FTP_PASS)
            ftp.cwd(config.FTP_REMOTE_DIR)

            for local_path, remote_subdir in files:
                if not os.path.isfile(local_path):
                    print(f"⚠️ Datei fehlt: {local_path}")
                    continue

                # in Unterverzeichnis wechseln (oder anlegen)
                try:
                    ftp.cwd(remote_subdir)
                except ftplib.error_perm:
                    print(f"🚧 Remote-Verzeichnis erstellen: {remote_subdir}")
                    ftp.mkd(remote_subdir)
                    ftp.cwd(remote_subdir)

                print(f"📤 Hochladen: {local_path} → /{config.FTP_REMOTE_DIR}/{remote_subdir}")
                with open(local_path, "rb") as f:
                    ftp.storbinary(f"STOR {os.path.basename(local_path)}", f)
                print(f"✅ Hochgeladen: {os.path.basename(local_path)} → /{remote_subdir}")

                # zurück ins Kamera-ID-Hauptverzeichnis
                ftp.cwd("..")

        return True

    except Exception as e:
        print(f"❌ Batch-FTP-Upload fehlgeschlagen: {e}")
        return False
