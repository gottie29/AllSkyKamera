# config.py - automatisch generiert

try:
    from askutils.ASKsecret import API_KEY, API_URL
except ImportError:
    API_KEY = API_URL = None

# Kameradaten
KAMERA_ID      = "TestASK2"
KAMERA_NAME    = "asd"
STANDORT_NAME  = "asd"
BENUTZER_NAME  = "asd"
KONTAKT_EMAIL  = ""
WEBSEITE       = ""

# Standortkoordinaten
LATITUDE       = 52.123
LONGITUDE      = 13.123

# Pfade
ALLSKY_PATH     = "/home/pi/allsky"
IMAGE_BASE_PATH = "images"
IMAGE_PATH      = "tmp"

# Objektiv- & SQM-Daten
PIX_SIZE_MM    = 0.00155
FOCAL_MM       = 1.85
ZP             = 6.0
SQM_PATCH_SIZE = 100

# Sensoren
BME280_ENABLED      = True
BME280_I2C_ADDRESS  = 0x76
BME280_OVERLAY      = True

TSL2591_ENABLED         = True
TSL2591_I2C_ADDRESS     = 0x29
TSL2591_SQM2_LIMIT      = 6.0
TSL2591_SQM_CORRECTION  = 0.0
TSL2591_OVERLAY         = True

DS18B20_ENABLED = True
DS18B20_OVERLAY = True

MLX90614_ENABLED = True
MLX90614_I2C_ADDRESS = 0x5A

KPINDEX_OVERLAY = True

ANALEMMA_ENABLED = True
KAMERA_WIDTH = 4056
KAMERA_HEIGHT = 3040
A_SHUTTER = 10       # 1 ms - deutlich kuerzer!
A_GAIN = 1.0           # Kein Gain
A_BRIGHTNESS = 0.0
A_CONTRAST = 0.0
A_SATURATION = 0.0
A_PATH = "/home/pi/AllSkyKamera/tmp"

# CRONTABS
CRONTABS = [
    {
        "comment": "Allsky Raspi-Status",
        "schedule": "*/1 * * * *",
        "command": "cd /home/pi/AllSkyKamera && python3 -m scripts.raspi_status"
    },
    {
        "comment": "Config Update",
        "schedule": "0 12 * * *",
        "command": "cd /home/pi/AllSkyKamera && python3 -m scripts.upload_config_json"
    },
    {
        "comment": "BME280 Sensor",
        "schedule": "*/1 * * * *",
        "command": "cd /home/pi/AllSkyKamera && python3 -m scripts.bme280_logger"
    },
    {
        "comment": "TSL2591 Sensor",
        "schedule": "*/1 * * * *",
        "command": "cd /home/pi/AllSkyKamera && python3 -m scripts.tsl2591_logger"
    },
    {
        "comment": "DS18B20 Sensor",
        "schedule": "*/1 * * * *",
        "command": "cd /home/pi/AllSkyKamera && python3 -m scripts.ds18b20_logger"
    },
    {
        "comment": "Generiere KPIndex Overlay variable",
        "schedule": "*/15 * * * *",
        "command": "cd /home/pi/AllSkyKamera && python3 -m scripts.kpindex_logger"
    },
    {
        "comment": "Generiere Analemma",
        "schedule": "54/11 * * * *",
        "command": "cd /home/pi/AllSkyKamera && python3 -m scripts.analemma"
    },
    {
        "comment": "Image FTP-Upload",
        "schedule": "*/2 * * * *",
        "command": "cd /home/pi/AllSkyKamera && python3 -m scripts.run_image_upload"
    },
    {
        "comment": "Nightly FTP-Upload",
        "schedule": "45 8 * * *",
        "command": "cd /home/pi/AllSkyKamera && python3 -m scripts.run_nightly_upload"
    },
    {
        "comment": "SQM Messung",
        "schedule": "*/5 * * * *",
        "command": "cd /home/pi/AllSkyKamera && python3 -m scripts.sqm_camera_logger"
    },
    {
        "comment": "SQM Plot Generierung",
        "schedule": "0 8 * * *",
        "command": "cd /home/pi/AllSkyKamera && python3 -m scripts.plot_sqm_night"
    }
]

###################################################################
# Nichts aendern !!!
###################################################################
FTP_VIDEO_DIR = "videos"
FTP_KEOGRAM_DIR = "keogram"
FTP_STARTRAIL_DIR = "startrails"
FTP_SQM_DIR = "sqm"
FTP_ANALEMMA_DIR = "analemma"

# Secrets laden
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
