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
    "LONGITUDE",
    "INDI",
]

OPTIONAL_FIELDS = [
    # -----------------------------
    # Kamera / Optik / SQM
    # -----------------------------
    "PIX_SIZE_MM",
    "FOCAL_MM",
    "ZP",
    "SQM_PATCH_SIZE",
    "KAMERA_WIDTH",
    "KAMERA_HEIGHT",

    # -----------------------------
    # Sensor-Flags, Namen, Parameter
    # -----------------------------
    "BME280_ENABLED",
    "BME280_NAME",
    "BME280_I2C_ADDRESS",
    "BME280_OVERLAY",
    "BME280_LOG_INTERVAL_MIN",
    # Offsets (NEU)
    "BME280_TEMP_OFFSET_C",
    "BME280_PRESS_OFFSET_HPA",
    "BME280_HUM_OFFSET_PCT",

    "TSL2591_ENABLED",
    "TSL2591_NAME",
    "TSL2591_I2C_ADDRESS",
    "TSL2591_SQM2_LIMIT",
    "TSL2591_SQM_CORRECTION",
    "TSL2591_OVERLAY",
    "TSL2591_LOG_INTERVAL_MIN",

    "DS18B20_ENABLED",
    "DS18B20_NAME",
    "DS18B20_OVERLAY",
    "DS18B20_LOG_INTERVAL_MIN",
    # Offset (NEU)
    "DS18B20_TEMP_OFFSET_C",

    "DHT11_ENABLED",
    "DHT11_NAME",
    "DHT11_GPIO_BCM",
    "DHT11_RETRIES",
    "DHT11_RETRY_DELAY",
    "DHT11_OVERLAY",
    "DHT11_LOG_INTERVAL_MIN",
    # Offsets (NEU)
    "DHT11_TEMP_OFFSET_C",
    "DHT11_HUM_OFFSET_PCT",

    "DHT22_ENABLED",
    "DHT22_NAME",
    "DHT22_GPIO_BCM",
    "DHT22_RETRIES",
    "DHT22_RETRY_DELAY",
    "DHT22_OVERLAY",
    "DHT22_LOG_INTERVAL_MIN",
    # Offsets (NEU)
    "DHT22_TEMP_OFFSET_C",
    "DHT22_HUM_OFFSET_PCT",

    "MLX90614_ENABLED",
    "MLX90614_NAME",
    "MLX90614_I2C_ADDRESS",
    "MLX90614_LOG_INTERVAL_MIN",
    # Offset (NEU)
    "MLX90614_AMBIENT_OFFSET_C",
    # Cloud-Koeffizienten (NEU)
    "MLX_CLOUD_K1",
    "MLX_CLOUD_K2",
    "MLX_CLOUD_K3",
    "MLX_CLOUD_K4",
    "MLX_CLOUD_K5",
    "MLX_CLOUD_K6",
    "MLX_CLOUD_K7",

    # -----------------------------
    # HTU21 / GY-21
    # -----------------------------
    "HTU21_ENABLED",
    "HTU21_NAME",
    "HTU21_I2C_ADDRESS",
    "HTU21_TEMP_OFFSET",
    "HTU21_HUM_OFFSET",
    "HTU21_OVERLAY",
    "HTU21_LOG_INTERVAL_MIN",

    # -----------------------------
    # SHT3x
    # -----------------------------
    "SHT3X_ENABLED",
    "SHT3X_NAME",
    "SHT3X_I2C_ADDRESS",
    "SHT3X_TEMP_OFFSET",
    "SHT3X_HUM_OFFSET",
    "SHT3X_OVERLAY",
    "SHT3X_LOG_INTERVAL_MIN",

    # -----------------------------
    # KpIndex / Analemma
    # -----------------------------
    "KPINDEX_ENABLED",
    "KPINDEX_OVERLAY",
    "KPINDEX_LOG_INTERVAL_MIN",

    "ANALEMMA_ENABLED",
    "A_SHUTTER",
    "A_GAIN",
    "A_BRIGHTNESS",
    "A_CONTRAST",
    "A_SATURATION",
]


def get_version():
    # version liegt im Projekt-root (cd ROOT && python3 -m scripts.upload_config_json)
    version_file = os.path.join("version")
    try:
        with open(version_file, "r", encoding="utf-8") as vf:
            return vf.read().strip()
    except Exception as e:
        error(f"Fehler beim Lesen der Version: {e}")
        return None


def _json_safe(value):
    """
    Macht Werte JSON-sicher:
    - bytes -> decode
    - I2C-Adressen (int) -> hex-string ("0x76")
    - sonst: unveraendert
    """
    try:
        if isinstance(value, (bytes, bytearray)):
            return value.decode("utf-8", errors="replace")

        # I2C Adressen: in config.py sind sie i.d.R. int-Literale (0x76 -> 118).
        # Exportieren wollen wir gerne "0x76" als String.
        if isinstance(value, int):
            # Heuristik: typische I2C 7-bit Range
            if 0x03 <= value <= 0x77:
                return f"0x{value:02x}"
            return value

        return value
    except Exception:
        return str(value)


def extract_config_data():
    data = {}

    # Pflichtfelder
    for key in EXPORT_FIELDS:
        if hasattr(config, key):
            data[key] = _json_safe(getattr(config, key))

    # Optionale Felder
    for opt in OPTIONAL_FIELDS:
        if hasattr(config, opt):
            data[opt] = _json_safe(getattr(config, opt))

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
        log(f"config.json wurde erstellt: {filename}")
        return filename
    except Exception as e:
        error(f"Fehler beim Schreiben der config.json: {e}")
        return None


def upload_to_ftp(filepath: str):
    # Schutz: FTP-Konfig muss vorhanden sein
    missing = []
    for k in ("FTP_SERVER", "FTP_USER", "FTP_PASS", "FTP_REMOTE_DIR"):
        if not hasattr(config, k) or not getattr(config, k):
            missing.append(k)

    if missing:
        error(f"FTP-Upload abgebrochen: folgende config-Werte fehlen/leer: {', '.join(missing)}")
        return False

    try:
        with ftplib.FTP(config.FTP_SERVER) as ftp:
            ftp.login(config.FTP_USER, config.FTP_PASS)
            ftp.cwd(config.FTP_REMOTE_DIR)
            with open(filepath, "rb") as f:
                ftp.storbinary(f"STOR {os.path.basename(filepath)}", f)
            log(f"Datei {filepath} erfolgreich per FTP hochgeladen.")
        return True
    except Exception as e:
        error(f"FTP-Upload fehlgeschlagen: {e}")
        return False
