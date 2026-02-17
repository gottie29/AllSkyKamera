#!/usr/bin/env bash
# Normalize possible CRLF line endings on first run
if command -v dos2unix >/dev/null 2>&1; then
    dos2unix "$0" >/dev/null 2>&1 || true
else
    sed -i 's/\r$//' "$0" || true
fi

set -euo pipefail
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
export PYTHONIOENCODING=UTF-8
export PYTHONUTF8=1

# --------------------------------------------------------------------
# 0. Basic checks
# --------------------------------------------------------------------
if [ ! -d "askutils" ]; then
    echo "This script must be executed in the project root (with askutils/)."
    exit 1
fi

PROJECT_ROOT="$(pwd)"
echo "Project root: ${PROJECT_ROOT}"

CFG_FILE="askutils/config.py"
SECRET_FILE="askutils/ASKsecret.py"

if [ -f "$CFG_FILE" ] || [ -f "$SECRET_FILE" ]; then
    echo
    echo "Existing configuration detected:"
    [ -f "$CFG_FILE" ] && echo " - ${CFG_FILE}"
    [ -f "$SECRET_FILE" ] && echo " - ${SECRET_FILE}"
    read -r -p "Do you want to backup and overwrite these files? (y/n): " OVERWRITE
    case "${OVERWRITE}" in
        [Yy]* )
            [ -f "$CFG_FILE" ] && mv "$CFG_FILE" "askutils/config.py.bak"
            [ -f "$SECRET_FILE" ] && mv "$SECRET_FILE" "askutils/ASKsecret.py.bak"
            echo "Old configuration files have been renamed to .bak."
            ;;
        * )
            echo "Keeping existing configuration. Installation aborted."
            exit 0
            ;;
    esac
fi

# --------------------------------------------------------------------
# 1. API key
# --------------------------------------------------------------------
echo
echo "=== 1. API access ==="
echo "To request an API key, please visit: https://allskykamera.space"
read -r -p "Do you already have an API key? (y/n): " HAS_KEY
case "${HAS_KEY}" in
    [Yy]* )
        ;;
    * )
        echo "Please request an API key at https://allskykamera.space and run this script again."
        exit 1
        ;;
esac

echo
read -r -p "API_KEY: " API_KEY

# Encoded API URL (base64) to avoid hardcoding plain text URL in the file
ENC_API_URL="aHR0cHM6Ly9hbGxza3lrYW1lcmEuc3BhY2UvZ2V0U2VjcmV0cy5waHA="
API_URL="$(printf '%s' "${ENC_API_URL}" | base64 -d)"

echo
echo "> Testing API access..."
if ! RESPONSE="$(curl -s --fail "${API_URL}?key=${API_KEY}")"; then
    echo "API URL or network error. Aborting."
    exit 1
fi

if echo "${RESPONSE}" | grep -q '"error"'; then
    ERRMSG="$(echo "${RESPONSE}" | sed -n 's/.*"error"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
    echo "API error: ${ERRMSG:-unknown}. Aborting."
    exit 1
fi

INFLUX_URL_FROM_API="$(echo "${RESPONSE}" | sed -n 's/.*"influx_url"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
KAMERA_ID_FROM_API="$(echo "${RESPONSE}" | sed -n 's/.*"kamera_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"

if [ -z "${INFLUX_URL_FROM_API}" ] || [ -z "${KAMERA_ID_FROM_API}" ]; then
    echo "Invalid API response. Aborting."
    exit 1
fi

echo "API access validated."
echo "Camera ID from server: ${KAMERA_ID_FROM_API}"

# --------------------------------------------------------------------
# 2. Which interface is installed? (TJ vs INDI)
# --------------------------------------------------------------------
echo
echo "=== 2. Allsky interface selection ==="
echo "Which interface do you use?"
echo "  1) Thomas Jacquin allsky interface (TJ)"
echo "  2) INDI AllSky interface"
read -r -p "Select [1/2] (default: 1): " IFACE_CHOICE
IFACE_CHOICE="${IFACE_CHOICE:-1}"

INDI_FLAG=0
CAMERAID_DETECTED="ccd_unknown"

if [ "${IFACE_CHOICE}" = "2" ]; then
    echo
    echo "> INDI interface selected."
    INDI_FLAG=1

    DEFAULT_ALLSKY_PATH="/var/www/html/allsky"

    while true; do
        echo
        read -r -p "Path to INDI allsky interface [default: ${DEFAULT_ALLSKY_PATH}]: " ALLSKY_PATH
        ALLSKY_PATH="${ALLSKY_PATH:-${DEFAULT_ALLSKY_PATH}}"

        INDI_IMAGES_DIR="${ALLSKY_PATH}/images"

        echo "> Checking INDI images dir: ${INDI_IMAGES_DIR}"

        if [ ! -d "${INDI_IMAGES_DIR}" ]; then
            echo "❌ Directory not found: ${INDI_IMAGES_DIR}"
            read -r -p "Try another path? (y/n): " RETRY
            [[ "${RETRY}" =~ ^[Yy]$ ]] || exit 1
            continue
        fi

        # Detect CAMERAID from directory name "ccd_*"
        CCD_DIR_NAME="$(find "${INDI_IMAGES_DIR}" -maxdepth 1 -type d -name 'ccd_*' -printf '%f\n' 2>/dev/null | sort | head -n 1 || true)"

        if [ -n "${CCD_DIR_NAME}" ]; then
            CAMERAID_DETECTED="${CCD_DIR_NAME}"
            echo "✅ Detected CAMERAID: ${CAMERAID_DETECTED}"
            break
        else
            echo "❌ No directory starting with 'ccd_' found in ${INDI_IMAGES_DIR}"
            read -r -p "Try another path? (y/n): " RETRY
            [[ "${RETRY}" =~ ^[Yy]$ ]] || exit 1
        fi
    done
else
    echo
    echo "> TJ interface selected."
    INDI_FLAG=0
    CAMERAID_DETECTED="ccd_unknown"

    echo
    echo "=== 2. Path to allsky interface ==="
    DEFAULT_ALLSKY_PATH="${HOME}/allsky"
    read -r -p "Path to allsky interface [default: ${DEFAULT_ALLSKY_PATH}]: " ALLSKY_PATH
    ALLSKY_PATH="${ALLSKY_PATH:-${DEFAULT_ALLSKY_PATH}}"
fi

echo "Using ALLSKY_PATH: ${ALLSKY_PATH}"
echo "INDI flag: ${INDI_FLAG}"
echo "CAMERAID: ${CAMERAID_DETECTED}"

# --------------------------------------------------------------------
# 3. Install system packages
# --------------------------------------------------------------------
echo
echo "=== 3. Installing system packages (requires sudo) ==="

# --- Recovery: handle interrupted dpkg state ---
echo "> Checking dpkg state..."
if ! sudo dpkg --audit >/dev/null 2>&1; then
  echo "> dpkg reports issues. Attempting recovery..."
fi

# If dpkg was interrupted previously, this will fix it
sudo dpkg --configure -a || true
sudo apt-get -f install -y || true

# Now do the normal update/install
sudo apt-get update

install_if_available() {
  local pkg="$1"
  if apt-cache show "$pkg" >/dev/null 2>&1; then
    sudo apt-get install -y "$pkg"
  else
    echo "Skipping optional package (not available): $pkg"
  fi
}

# Pflichtpakete
sudo apt-get install -y \
  python3-pip python3-venv python3-smbus i2c-tools raspi-config \
  python3-psutil python3-pil curl dos2unix whiptail

# optional / distro-abhängig
install_if_available python3-libgpiod
install_if_available python3-gpiod
install_if_available libopenblas-dev

# --------------------------------------------------------------------
# 4. Enable interfaces (non-interactive)
# --------------------------------------------------------------------
echo
echo "=== 4. Enabling I2C, 1-Wire and camera (if supported) ==="
if sudo raspi-config nonint do_i2c 0 >/dev/null 2>&1; then
    echo "I2C enabled."
else
    echo "I2C configuration skipped."
fi

if sudo raspi-config nonint do_1wire 0 >/dev/null 2>&1; then
    echo "1-Wire enabled."
else
    echo "1-Wire configuration skipped."
fi

if sudo raspi-config nonint do_camera 0 >/dev/null 2>&1; then
    echo "Camera enabled."
else
    echo "Camera configuration skipped (may not be supported on this system)."
fi

# --------------------------------------------------------------------
# 5. Python dependencies
# --------------------------------------------------------------------
echo
echo "=== 5. Installing Python dependencies (user scope) ==="
pip3 install --user \
    influxdb-client \
    adafruit-circuitpython-tsl2591 \
    adafruit-circuitpython-dht \
    requests \
    pillow \
    numpy \
    matplotlib \
    smbus2 \
    --break-system-packages

# --------------------------------------------------------------------
# 6. Create askutils/ASKsecret.py
# --------------------------------------------------------------------
echo
echo "=== 6. Creating askutils/ASKsecret.py ==="
cat > "${SECRET_FILE}" <<EOF
import base64

# Automatically generated file - do not commit to git!
API_KEY = "${API_KEY}"
ENC_API_URL = "${ENC_API_URL}"
API_URL = base64.b64decode(ENC_API_URL).decode()
EOF

echo "Created ${SECRET_FILE}"

# --------------------------------------------------------------------
# 7. Create a minimal default askutils/config.py
#    Detailed configuration will be done via ./setup.sh
# --------------------------------------------------------------------
echo
echo "=== 7. Creating minimal askutils/config.py ==="

cat > "${CFG_FILE}" <<EOF
# config.py - automatically generated by install.sh

try:
    from askutils.ASKsecret import API_KEY, API_URL
except ImportError:
    API_KEY = None
    API_URL = None

# Basic camera data (will be overwritten by setup.sh if you run it)
KAMERA_ID      = "${KAMERA_ID_FROM_API}"
KAMERA_NAME    = "My AllSky Camera"
STANDORT_NAME  = "My location"
BENUTZER_NAME  = "Operator"
KONTAKT_EMAIL  = ""
WEBSEITE       = ""

# Location coordinates (example values, change with setup.sh)
LATITUDE       = 52.0
LONGITUDE      = 13.0

# Paths
ALLSKY_PATH     = "${ALLSKY_PATH}"
IMAGE_BASE_PATH = "images"
IMAGE_PATH      = "tmp"
INDI            = ${INDI_FLAG}
CAMERAID        = "${CAMERAID_DETECTED}"

# Optics and SQM defaults
PIX_SIZE_MM    = 0.00155
FOCAL_MM       = 1.85
ZP             = 6.0
SQM_PATCH_SIZE = 100

# --------------------------------------------------------------------
# Sensors: disabled by default, setup.sh will enable and configure them
# --------------------------------------------------------------------

# BME280
BME280_ENABLED          = False
BME280_NAME             = "BME280"
BME280_I2C_ADDRESS      = 0x76
BME280_OVERLAY          = False
BME280_TEMP_OFFSET_C    = 0.0
BME280_PRESS_OFFSET_HPA = 0.0
BME280_HUM_OFFSET_PCT   = 0.0

# TSL2591
TSL2591_ENABLED        = False
TSL2591_NAME           = "TSL2591"
TSL2591_I2C_ADDRESS    = 0x29
TSL2591_SQM2_LIMIT     = 0.0
TSL2591_SQM_CORRECTION = 0.0
TSL2591_OVERLAY        = False

# DS18B20
DS18B20_ENABLED        = False
DS18B20_NAME           = "DS18B20"
DS18B20_OVERLAY        = False
DS18B20_TEMP_OFFSET_C  = 0.0

# DHT11
DHT11_ENABLED          = False
DHT11_NAME             = "DHT11"
DHT11_GPIO_BCM         = 6
DHT11_RETRIES          = 10
DHT11_RETRY_DELAY      = 0.3
DHT11_OVERLAY          = False
DHT11_TEMP_OFFSET_C    = 0.0
DHT11_HUM_OFFSET_PCT   = 0.0

# DHT22
DHT22_ENABLED          = False
DHT22_NAME             = "DHT22"
DHT22_GPIO_BCM         = 6
DHT22_RETRIES          = 10
DHT22_RETRY_DELAY      = 0.3
DHT22_OVERLAY          = False
DHT22_TEMP_OFFSET_C    = 0.0
DHT22_HUM_OFFSET_PCT   = 0.0

# MLX90614
MLX90614_ENABLED            = False
MLX90614_NAME               = "MLX90614"
MLX90614_I2C_ADDRESS        = 0x5a
MLX90614_AMBIENT_OFFSET_C   = 0.0
# optional clamp defaults (safe to keep even if script ignores them)
MLX90614_AMBIENT_MIN_C      = -40.0
MLX90614_AMBIENT_MAX_C      = 85.0

# HTU21 / GY-21
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

# --------------------------------------------------------------------
# Logger intervals in minutes
# --------------------------------------------------------------------
BME280_LOG_INTERVAL_MIN   = 1
TSL2591_LOG_INTERVAL_MIN  = 1
DS18B20_LOG_INTERVAL_MIN  = 1
DHT11_LOG_INTERVAL_MIN    = 1
DHT22_LOG_INTERVAL_MIN    = 1
MLX90614_LOG_INTERVAL_MIN = 1
HTU21_LOG_INTERVAL_MIN    = 1
SHT3X_LOG_INTERVAL_MIN    = 1

# KpIndex / Analemma / camera
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
A_PATH = "${PROJECT_ROOT}/tmp"

# --------------------------------------------------------------------
# CRONTABS - base jobs
# --------------------------------------------------------------------
CRONTABS = [
    {
        "comment": "Allsky Raspi status",
        "schedule": "*/1 * * * *",
        "command": "cd ${PROJECT_ROOT} && python3 -m scripts.raspi_status",
    },
    {
        "comment": "Allsky image upload",
        "schedule": "*/2 * * * *",
        "command": "cd ${PROJECT_ROOT} && python3 -m scripts.run_image_upload",
    },
    {
        "comment": "Config update",
        "schedule": "0 12 * * *",
        "command": "cd ${PROJECT_ROOT} && python3 -m scripts.upload_config_json",
    },
    {
        "comment": "Nightly FTP upload",
        "schedule": "45 8 * * *",
        "command": "cd ${PROJECT_ROOT} && python3 -m scripts.run_nightly_upload",
    },
    {
        "comment": "SQM measurement",
        "schedule": "*/5 * * * *",
        "command": "cd ${PROJECT_ROOT} && python3 -m scripts.sqm_camera_logger",
    },
    {
        "comment": "SQM plot generation",
        "schedule": "0 8 * * *",
        "command": "cd ${PROJECT_ROOT} && python3 -m scripts.plot_sqm_night",
    },
]

# Sensor logger cronjobs will be added dynamically by setup.sh
# based on the *_ENABLED flags and *_LOG_INTERVAL_MIN values.

###################################################################
# Do not change below this line
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
EOF

echo "Created ${CFG_FILE}"

# --------------------------------------------------------------------
# 8. Optional: FTP upload test and initial config upload
# --------------------------------------------------------------------
echo
read -r -p "Run FTP upload test now (tests/ftp_upload_test.py)? (y/n): " RUN_FTP_TEST
if [ "${RUN_FTP_TEST}" = "y" ] || [ "${RUN_FTP_TEST}" = "Y" ]; then
    if python3 tests/ftp_upload_test.py; then
        echo "FTP upload test finished."
    else
        echo "FTP upload test failed. Please check the output above."
    fi
fi

echo
read -r -p "Upload config.json now and install cronjobs? (y/n): " RUN_SETUP
if [ "${RUN_SETUP}" = "y" ] || [ "${RUN_SETUP}" = "Y" ]; then
    cd "${PROJECT_ROOT}"
    python3 -m scripts.upload_config_json || echo "upload_config_json failed."
    python3 -m scripts.manage_crontabs || echo "manage_crontabs failed."
fi

echo
echo "Installation finished."
echo "Next steps:"
echo "  1) Run ./setup.sh to configure camera, sensors and intervals."
echo "  2) After setup.sh, your configuration will be uploaded and cronjobs will be updated."
