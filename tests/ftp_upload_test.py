#!/usr/bin/env python3
import os
import sys
import ftplib

# Damit wir askutils aus dem Parent-Verzeichnis importieren koennen:
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
sys.path.insert(0, PROJECT_ROOT)

from askutils import config
from askutils.uploader.image_upload import upload_image

def test_config():
    required = [
        "FTP_SERVER",
        "FTP_USER",
        "FTP_PASS",
        "FTP_REMOTE_DIR",
        "ALLSKY_PATH",
        "IMAGE_BASE_PATH",
        "IMAGE_PATH",
    ]
    missing = [var for var in required if not getattr(config, var, None)]
    if missing:
        print(f"Fehlende Konfigurationswerte: {', '.join(missing)}")
        sys.exit(1)
    print("Konfigurationswerte sind vorhanden.")

def test_ftp_connection():
    try:
        ftp = ftplib.FTP(config.FTP_SERVER, timeout=10)
        ftp.login(config.FTP_USER, config.FTP_PASS)
        print(f"FTP-Login erfolgreich bei {config.FTP_SERVER}.")
        ftp.cwd(config.FTP_REMOTE_DIR)
        print(f"Wechsel ins Remote-Verzeichnis '{config.FTP_REMOTE_DIR}' erfolgreich.")
        listing = ftp.nlst()
        print(f"Aktueller Verzeichnisinhalt: {listing}")
        ftp.quit()
    except Exception as e:
        print(f"FTP-Verbindung oder Verzeichniszugriff fehlgeschlagen: {e}")
        sys.exit(1)

def test_image_upload():
    # Erstelle Dummy-Datei im tmp-Verzeichnis
    tmp_dir = os.path.join(config.ALLSKY_PATH, config.IMAGE_PATH)
    os.makedirs(tmp_dir, exist_ok=True)
    test_file = os.path.join(tmp_dir, "test_upload.txt")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("FTP-Upload Test\n")
    print(f"Testdatei erstellt: {test_file}")

    # Hochladen testen
    success = upload_image(test_file)
    if not success:
        print(" upload_image() fehlgeschlagen.")
        sys.exit(1)
    print(" upload_image() erfolgreich.")

    # Testdatei remote wieder loeschen
    try:
        ftp = ftplib.FTP(config.FTP_SERVER, timeout=10)
        ftp.login(config.FTP_USER, config.FTP_PASS)
        ftp.cwd(config.FTP_REMOTE_DIR)
        ftp.delete(os.path.basename(test_file))
        print(f"Testdatei remote geloescht: {os.path.basename(test_file)}")
        ftp.quit()
    except Exception as e:
        print(f"Konnte Testdatei remote nicht loeschen: {e}")

if __name__ == "__main__":
    print("== 1. Teste Konfiguration ==")
    test_config()
    print("\n== 2. Teste FTP-Verbindung ==")
    test_ftp_connection()
    print("\n== 3. Teste image_upload-Funktion ==")
    test_image_upload()
    print("\n Alle FTP-Tests erfolgreich abgeschlossen.")
