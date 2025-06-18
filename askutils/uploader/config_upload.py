# askutils/uploader/config_upload.py

import json
import ftplib
from askutils import config
from askutils.utils.logger import log, error

# Nur diese Felder werden öffentlich exportiert
EXPORT_FIELDS = [
    "KAMERA_ID",
    "KAMERA_NAME",
    "STANDORT_NAME",
    "BENUTZER_NAME",
    "KONTAKT_EMAIL",
    "LATITUDE",
    "LONGITUDE"
]

# Optional exportierte Felder – nur wenn vorhanden
OPTIONAL_FIELDS = [
    "BME280_ENABLED",
    "TSL2591_ENABLED"
]

def extract_config_data():
    data = {
        key: getattr(config, key)
        for key in EXPORT_FIELDS
        if hasattr(config, key)
    }

    # Füge optionale Felder hinzu, wenn sie existieren
    for opt in OPTIONAL_FIELDS:
        if hasattr(config, opt):
            data[opt] = getattr(config, opt)

    return data

def create_config_json(filename="config.json"):
    data = extract_config_data()

    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        log(f"📄 config.json wurde erstellt: {filename}")
        return filename
    except Exception as e:
        error(f"Fehler beim Schreiben der config.json: {e}")
        return None

def upload_to_ftp(filepath):
    try:
        with ftplib.FTP(config.FTP_SERVER) as ftp:
            ftp.login(config.FTP_USER, config.FTP_PASS)
            ftp.cwd(config.FTP_REMOTE_DIR)
            with open(filepath, "rb") as f:
                ftp.storbinary(f"STOR {filepath}", f)
            log(f"✅ Datei {filepath} erfolgreich per FTP hochgeladen.")
    except Exception as e:
        error(f"❌ FTP-Upload fehlgeschlagen: {e}")
