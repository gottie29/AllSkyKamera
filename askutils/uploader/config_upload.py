# askutils/uploader/config_upload.py

import json
import ftplib
import os
import time
import random
from askutils import config
from askutils.utils.logger import log, error

# Influx Writer (wie bei raspi_status)
try:
    from askutils.utils import influx_writer
except Exception:
    influx_writer = None


def _log_upload_status_to_influx(value: int) -> None:
    """
    Schreibt Upload-Status in Influx:
    measurement = uploadstatus
    tag kamera = ASKxxx
    field configupload:
      1 = upload_ok
      2 = upload_aborted_or_failed
      3 = file_not_found
      4 = file_too_old  (optional, falls du den Check aktivierst)
    """
    try:
        if influx_writer is None:
            return

        kamera_id = getattr(config, "KAMERA_ID", None) or getattr(config, "KAMERA", None)
        if not kamera_id:
            return

        influx_writer.log_metric(
            "uploadstatus",
            {"configupload": float(value)},
            tags={"host": "host1", "kamera": str(kamera_id)}
        )
    except Exception:
        # Logging darf nie den Upload abbrechen
        pass


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


def _safe_int(val, default: int) -> int:
    try:
        return int(val)
    except Exception:
        return default


def _apply_initial_jitter() -> None:
    """
    Jitter vor dem Upload, um gleichzeitige Peaks zu vermeiden.
    Default: 180 Sekunden
    Konfig: CONFIG_UPLOAD_JITTER_MAX_SECONDS
    """
    max_s = _safe_int(getattr(config, "CONFIG_UPLOAD_JITTER_MAX_SECONDS", 180), 180)
    if max_s <= 0:
        return

    delay = random.randint(0, max_s)
    if delay > 0:
        log(f"config_upload jitter_seconds={delay}")
        time.sleep(delay)


def _sleep_retry_window(min_s: int = 120, max_s: int = 300) -> int:
    """
    Wartefenster zwischen Retries, standardmaessig 2-5 Minuten.
    """
    delay = random.randint(min_s, max_s)
    log(f"config_upload retry_sleep_seconds={delay}")
    time.sleep(delay)
    return delay


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
        log(f"config_upload created_json file={filename}")
        return filename
    except Exception as e:
        error(f"Fehler beim Schreiben der config.json: {e}")
        return None


def _upload_once(filepath: str) -> None:
    """
    Fuehrt einen einzelnen FTP Upload aus oder wirft Exception.
    """
    with ftplib.FTP(config.FTP_SERVER) as ftp:
        # kleine Timeouts helfen gegen haengende Verbindungen
        try:
            ftp.connect(host=config.FTP_SERVER, timeout=30)
            ftp.login(config.FTP_USER, config.FTP_PASS)
        except TypeError:
            ftp.login(config.FTP_USER, config.FTP_PASS)

        ftp.cwd(config.FTP_REMOTE_DIR)
        with open(filepath, "rb") as f:
            ftp.storbinary(f"STOR {os.path.basename(filepath)}", f)


def upload_to_ftp(filepath: str) -> bool:
    """
    Upload mit:
    - Initial Jitter (Default 180s)
    - Retry bei Fehler mit Pause 2-5 Minuten

    Konfig-Parameter (optional in config.py):
    - CONFIG_UPLOAD_JITTER_MAX_SECONDS (Default 180)
    - CONFIG_UPLOAD_MAX_RETRIES (Default 3)
    - CONFIG_UPLOAD_RETRY_MIN_SECONDS (Default 120)
    - CONFIG_UPLOAD_RETRY_MAX_SECONDS (Default 300)
    """

    # Schutz: FTP-Konfig muss vorhanden sein
    missing = []
    for k in ("FTP_SERVER", "FTP_USER", "FTP_PASS", "FTP_REMOTE_DIR"):
        if not hasattr(config, k) or not getattr(config, k):
            missing.append(k)

    if missing:
        error(f"FTP-Upload abgebrochen: folgende config-Werte fehlen/leer: {', '.join(missing)}")
        _log_upload_status_to_influx(2)
        return False

    if not filepath or not os.path.isfile(filepath):
        error(f"FTP-Upload abgebrochen: Datei nicht gefunden: {filepath}")
        _log_upload_status_to_influx(3)
        return False

    # Optionaler "zu alt" Check (deaktiviert wenn <= 0)
    # Falls du das nutzen willst: CONFIG_UPLOAD_MAX_AGE_SECONDS in config.py setzen.
    max_age = _safe_int(getattr(config, "CONFIG_UPLOAD_MAX_AGE_SECONDS", 0), 0)
    if max_age > 0:
        try:
            age = time.time() - os.path.getmtime(filepath)
            if age > max_age:
                error(f"config_upload file_too_old age_seconds={int(age)} max_age_seconds={max_age} file={filepath}")
                _log_upload_status_to_influx(4)
                return False
        except Exception:
            # Wenn mtime nicht lesbar, lieber normal weitermachen
            pass

    # Initial Jitter (einmal pro Aufruf)
    _apply_initial_jitter()

    max_retries = _safe_int(getattr(config, "CONFIG_UPLOAD_MAX_RETRIES", 3), 3)
    retry_min_s = _safe_int(getattr(config, "CONFIG_UPLOAD_RETRY_MIN_SECONDS", 120), 120)
    retry_max_s = _safe_int(getattr(config, "CONFIG_UPLOAD_RETRY_MAX_SECONDS", 300), 300)
    if retry_max_s < retry_min_s:
        retry_max_s = retry_min_s

    attempt = 0
    while True:
        attempt += 1
        try:
            _upload_once(filepath)
            log(f"config_upload upload_ok attempt={attempt} file={os.path.basename(filepath)} remote_dir={config.FTP_REMOTE_DIR}")
            _log_upload_status_to_influx(1)
            return True
        except Exception as e:
            error(f"config_upload upload_fail attempt={attempt} error={e}")

            if attempt > max_retries:
                error(f"config_upload giving_up attempts={attempt} max_retries={max_retries}")
                _log_upload_status_to_influx(2)
                return False

            # Pause 2-5 Minuten (oder konfiguriert)
            _sleep_retry_window(retry_min_s, retry_max_s)
