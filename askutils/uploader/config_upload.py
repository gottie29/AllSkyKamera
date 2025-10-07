# askutils/uploader/config_upload.py

import json
import ftplib
import os
from askutils import config
from askutils.utils.logger import log, error

# Nur diese Felder werden oeffentlich exportiert
EXPORT_FIELDS = [
    "KAMERA_ID",
    "KAMERA_NAME",
    "STANDORT_NAME",
    "BENUTZER_NAME",
    "KONTAKT_EMAIL",
	"WEBSEITE",
    "LATITUDE",
    "LONGITUDE"
]

# Optional exportierte Felder - nur wenn vorhanden
OPTIONAL_FIELDS = [
    "BME280_ENABLED",
    "TSL2591_ENABLED",
	"DS18B20_ENABLED"
]

def get_version():
    # Hole den Pfad zum Projektordner (eine Ebene ueber askutils)
    version_file = os.path.join("version")
    try:
        with open(version_file, "r", encoding="utf-8") as vf:
            return vf.read().strip()
    except Exception as e:
        error(f"Fehler beim Lesen der Version: {e}")
        return None

def extract_config_data():
    data = {
        key: getattr(config, key)
        for key in EXPORT_FIELDS
        if hasattr(config, key)
    }

    # Fuege optionale Felder hinzu, wenn sie existieren
    for opt in OPTIONAL_FIELDS:
        if hasattr(config, opt):
            data[opt] = getattr(config, opt)

    # Version hinzufuegen
    version = get_version()
    if version:
        data["VERSION"] = version

    return data

def create_config_json(filename="config.json"):
    data = extract_config_data()

    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        log(f" config.json wurde erstellt: {filename}")
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
            log(f"Datei {filepath} erfolgreich per FTP hochgeladen.")
    except Exception as e:
        error(f" FTP-Upload fehlgeschlagen: {e}")
