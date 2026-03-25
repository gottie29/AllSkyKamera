# config.py - automatisch generiert

try:
    from askutils.ASKsecret import API_KEY, API_URL
except ImportError:
    API_KEY = API_URL = None

# Kameradaten
KAMERA_ID      = "ASK997"
KAMERA_NAME = 'My AllSky Camera'
STANDORT_NAME = 'My location'
BENUTZER_NAME = 'Stefan1'
KONTAKT_EMAIL = ''
WEBSEITE = ''

# Standortkoordinaten
LATITUDE = 52.1
LONGITUDE = 13.1

# Pfade
ALLSKY_PATH = '/home/pi/allsky'
IMAGE_BASE_PATH = 'images'
IMAGE_PATH = 'tmp/current_images'
IMAGE_UPLOAD_SCRIPT = "scripts.run_image_upload_tj_api"
NIGHTLY_UPLOAD_SCRIPT = "scripts.run_nightly_upload_tj_api"
INDI            = 0
CAMERAID = 'ccd_unknown'

# Objektiv- & SQM-Daten
PIX_SIZE_MM    = 0.00155
FOCAL_MM       = 1.85
ZP             = 6.0
SQM_PATCH_SIZE = 100

# Sensoren
# Sensoren
BME280_ENABLED = True

BME280_SENSORS = [
    {
        "enabled": True,
        "name": "Inside BME280 1Sensor",
        "address": 0x76,
        "overlay": True,
        "temp_offset_c": 0.0,
        "press_offset_hpa": 0.0,
        "hum_offset_pct": 0.0,
    },
    {
        "enabled": True,
        "name": "Outside BME280 2Sensor",
        "address": 0x77,
        "overlay": True,
        "temp_offset_c": 0.0,
        "press_offset_hpa": 0.0,
        "hum_offset_pct": 0.0,
    }
]

TSL2591_ENABLED        = False
TSL2591_NAME           = "TSL2591"
TSL2591_I2C_ADDRESS    = 0x29
TSL2591_SQM2_LIMIT     = 0.0
TSL2591_SQM_CORRECTION = 0.0
TSL2591_OVERLAY        = False

DS18B20_ENABLED  = False
DS18B20_NAME     = "DS18B20"
DS18B20_OVERLAY  = False
DS18B20_TEMP_OFFSET_C = 0.0

# DHT11
DHT11_ENABLED      = False
DHT11_NAME         = "DHT11"
DHT11_GPIO_BCM     = 6
DHT11_RETRIES      = 10
DHT11_RETRY_DELAY  = 0.3
DHT11_OVERLAY      = False
DHT11_TEMP_OFFSET_C    = 0.0
DHT11_HUM_OFFSET_PCT   = 0.0


# ---------------------------------------------------
# Meteor detection
# ---------------------------------------------------

METEOR_ENABLE = True

# Lokales Arbeits-/Ergebnisverzeichnis
METEOR_OUTPUT_DIR = "/home/pi/AllSkyKamera/meteordetect"

# State-Datei für inkrementelle Verarbeitung
METEOR_STATE_FILE = "/home/pi/AllSkyKamera/meteordetect/meteor_state.json"

# Lokale Aufbewahrung in Tagen
METEOR_KEEP_DAYS_LOCAL = 3

# Schwellwerte
METEOR_THRESHOLD = 80
METEOR_MIN_PIXELS = 1200
METEOR_MIN_BLOB_PIXELS = 25
METEOR_MIN_LINE_LENGTH = 20
METEOR_MIN_ASPECT_RATIO = 4.0

# Bildgrößen für Speicherung / Upload
METEOR_FULLHD_WIDTH = 1920
METEOR_SMALL_WIDTH = 640
METEOR_DIFF_WIDTH = 640
METEOR_BOXED_WIDTH = 640
METEOR_PREV_SMALL_WIDTH = 640

# Upload-Jitter innerhalb des 10-Minuten-Fensters
METEOR_UPLOAD_JITTER_MAX_SECONDS = 90




# DHT22
DHT22_ENABLED = True

DHT22_SENSORS = [
    {
        "enabled": True,
        "name": "DHT22 Sensor 1",
        "gpio_bcm": 6,
        "retries": 5,
        "retry_delay": 0.3,
        "overlay": True,
        "temp_offset_c": 0.0,
        "hum_offset_pct": 0.0,
    },
    {
        "enabled": True,
        "name": "Outside DHT22 Sensor 2",
        "gpio_bcm": 5,
        "retries": 5,
        "retry_delay": 0.3,
        "overlay": True,
        "temp_offset_c": 0.0,
        "hum_offset_pct": 0.0,
    }
]

MLX90614_ENABLED     = False
MLX90614_NAME        = "MLX90614"
MLX90614_I2C_ADDRESS = 0x5a
MLX90614_AMBIENT_OFFSET_C   = 0.0
MLX_CLOUD_K1 = 100.0
MLX_CLOUD_K2 = 0.0
MLX_CLOUD_K3 = 0.0
MLX_CLOUD_K4 = 0.0
MLX_CLOUD_K5 = 0.0
MLX_CLOUD_K6 = 0.0
MLX_CLOUD_K7 = 0.0

HTU21_ENABLED       = False
HTU21_NAME          = "HTU21 / GY-21"
HTU21_I2C_ADDRESS   = 0x40
HTU21_TEMP_OFFSET   = 0.0
HTU21_HUM_OFFSET    = 0.0
HTU21_OVERLAY       = False

# SHT3X Series (SHT30 / SHT31 / SHT35)
SHT3X_ENABLED       = False
SHT3X_NAME          = "SHT3x"
SHT3X_I2C_ADDRESS   = 0x44
SHT3X_TEMP_OFFSET   = 0.0
SHT3X_HUM_OFFSET    = 0.0
SHT3X_OVERLAY       = False

# Logger-Intervalle in Minuten
BME280_LOG_INTERVAL_MIN   = 1
TSL2591_LOG_INTERVAL_MIN  = 1
DS18B20_LOG_INTERVAL_MIN  = 1
DHT11_LOG_INTERVAL_MIN    = 1
DHT22_LOG_INTERVAL_MIN    = 1
MLX90614_LOG_INTERVAL_MIN = 1
HTU21_LOG_INTERVAL_MIN    = 1
SHT3X_LOG_INTERVAL_MIN    = 1

# KpIndex / Analemma / Kamera
KPINDEX_ENABLED = False
KPINDEX_OVERLAY = False
KPINDEX_LOG_INTERVAL_MIN = 15

ANALEMMA_ENABLED = False
KAMERA_WIDTH = 4056
KAMERA_HEIGHT = 3040
A_SHUTTER = 10
A_GAIN = 1.0
A_BRIGHTNESS = 0.0
A_CONTRAST = 0.0
A_SATURATION = 0.0
A_PATH = "/home/pi/AllSkyKamera/tmp"

# CRONTABS – Basisjobs
CRONTABS = [
    {
        "comment": "Allsky Raspi-Status",
        "schedule": "*/1 * * * *",
        "command": "cd /home/pi/AllSkyKamera && /usr/bin/python3 -m scripts.raspi_status",
    },
    {
        "comment": "Allsky Image-Upload API",
        "schedule": "*/2 * * * *",
        "command": "cd /home/pi/AllSkyKamera && /usr/bin/python3 -m scripts.run_image_upload_tj_api",
    },
    {
        "comment": "Config Update",
        "schedule": "0 12 * * *",
        "command": "cd /home/pi/AllSkyKamera && /usr/bin/python3 -m scripts.upload_config_json",
    },
    {
        "comment": "Nightly API-Upload",
        "schedule": "45 8 * * *",
        "command": "cd /home/pi/AllSkyKamera && /usr/bin/python3 -m scripts.run_nightly_upload_tj_api",
    },
    {
        "comment": "SQM Messung",
        "schedule": "*/5 * * * *",
        "command": "cd /home/pi/AllSkyKamera && /usr/bin/python3 -m scripts.sqm_camera_logger",
    },
]

if not INDI:
    CRONTABS.append({
        "comment": "TJ Settings Upload",
        "schedule": "*/10 * * * *",
        "command": "cd /home/pi/AllSkyKamera && /usr/bin/python3 -m scripts.run_tj_settings_upload",
    })

if INDI:
    CRONTABS.append({
        "comment": "INDI Settings Upload",
        "schedule": "*/10 * * * *",
        "command": "cd /home/pi/AllSkyKamera && /usr/bin/python3 -m scripts.run_indi_settings_upload",
    })

if BME280_ENABLED:
    CRONTABS.append({
        "comment": "BME280 Sensor",
        "schedule": f"*/{BME280_LOG_INTERVAL_MIN} * * * *",
        "command": "cd /home/pi/AllSkyKamera && /usr/bin/python3 -m scripts.bme280_logger",
    })

if DS18B20_ENABLED:
    CRONTABS.append({
        "comment": "DS18B20 Sensor",
        "schedule": f"*/{DS18B20_LOG_INTERVAL_MIN} * * * *",
        "command": "cd /home/pi/AllSkyKamera && /usr/bin/python3 -m scripts.ds18b20_logger",
    })

if TSL2591_ENABLED:
    CRONTABS.append({
        "comment": "TSL2591 Sensor",
        "schedule": f"*/{TSL2591_LOG_INTERVAL_MIN} * * * *",
        "command": "cd /home/pi/AllSkyKamera && /usr/bin/python3 -m scripts.tsl2591_logger",
    })

if MLX90614_ENABLED:
    CRONTABS.append({
        "comment": "MLX90614 Sensor",
        "schedule": f"*/{MLX90614_LOG_INTERVAL_MIN} * * * *",
        "command": "cd /home/pi/AllSkyKamera && /usr/bin/python3 -m scripts.mlx90614_logger",
    })

if DHT11_ENABLED:
    CRONTABS.append({
        "comment": "DHT11 Sensor",
        "schedule": f"*/{DHT11_LOG_INTERVAL_MIN} * * * *",
        "command": "cd /home/pi/AllSkyKamera && /usr/bin/python3 -m scripts.dht11_logger",
    })

if DHT22_ENABLED:
    CRONTABS.append({
        "comment": "DHT22 Sensor",
        "schedule": f"*/{DHT22_LOG_INTERVAL_MIN} * * * *",
        "command": "cd /home/pi/AllSkyKamera && /usr/bin/python3 -m scripts.dht22_logger",
    })

if HTU21_ENABLED:
    CRONTABS.append({
        "comment": "HTU21 / GY-21 Sensor",
        "schedule": f"*/{HTU21_LOG_INTERVAL_MIN} * * * *",
        "command": "cd /home/pi/AllSkyKamera && /usr/bin/python3 -m scripts.htu21_logger",
    })

if SHT3X_ENABLED:
    CRONTABS.append({
        "comment": "SHT3x Sensor",
        "schedule": f"*/{SHT3X_LOG_INTERVAL_MIN} * * * *",
        "command": "cd /home/pi/AllSkyKamera && /usr/bin/python3 -m scripts.sht3x_logger",
    })

if KPINDEX_ENABLED:
    CRONTABS.append({
        "comment": "KpIndex Logger",
        "schedule": f"*/{KPINDEX_LOG_INTERVAL_MIN} * * * *",
        "command": "cd /home/pi/AllSkyKamera && /usr/bin/python3 -m scripts.kpindex_logger",
    })

###################################################################
# Nichts aendern !!!
###################################################################
FTP_VIDEO_DIR      = "videos"
FTP_KEOGRAM_DIR    = "keogram"
FTP_STARTRAIL_DIR  = "startrails"
FTP_SQM_DIR        = "sqm"
FTP_ANALEMMA_DIR   = "analemma"
FTP_STARTRAILSVIDEO_DIR = "startrailsvideo"

from askutils.utils.load_secrets import load_remote_secrets
_secrets = load_remote_secrets(API_KEY, API_URL)
if _secrets:
    INFLUX_URL     = _secrets["INFLUX_URL"]
    INFLUX_TOKEN   = _secrets["INFLUX_TOKEN"]
    INFLUX_ORG     = _secrets["INFLUX_ORG"]
    INFLUX_BUCKET  = _secrets["INFLUX_BUCKET"]
    FTP_USER       = _secrets["FTP_USER"]
    FTP_PASS       = _secrets["FTP_PASS"]
    FTP_SERVER     = _secrets["FTP_SERVER"]
    FTP_REMOTE_DIR = _secrets["FTP_REMOTE_DIR"]
    KAMERA_ID      = _secrets["KAMERA_ID"]
else:
    INFLUX_URL = INFLUX_TOKEN = INFLUX_ORG = INFLUX_BUCKET = None
    FTP_USER = FTP_PASS = FTP_SERVER = FTP_REMOTE_DIR = None
