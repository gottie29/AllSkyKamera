#!/usr/bin/env bash
# Entfernt versehentliche CRLF-Zeilenenden bei Aufruf
if command -v dos2unix &>/dev/null; then
    dos2unix "$0" &>/dev/null || true
else
    sed -i 's/\r$//' "$0" || true
fi

set -euo pipefail

# Dieses Skript installiert und konfiguriert die AllSky-Kamera-Software.
# Muss im Projekt-Root (mit askutils/) ausgeführt werden.

if [ ! -d "askutils" ]; then
    echo "❌ Dieses Skript muss im Projekt-Root (mit askutils/) aufgerufen werden."
    exit 1
fi

PROJECT_ROOT="$(pwd)"
echo "Arbeitsverzeichnis: $PROJECT_ROOT"

echo
echo "Um einen API-Key zu erhalten, besuchen Sie: https://allskykamera.space"
read -r -p "Haben Sie bereits einen API-Key? (y/n): " HAS_KEY
case "$HAS_KEY" in
    [Yy]* ) ;;
    * )
        echo "Bitte beantragen Sie einen API-Key auf https://allskykamera.space und führen Sie das Skript erneut aus."
        exit 1
        ;;
esac

# 0. API_KEY abfragen und testen
echo
echo "=== 0. API-Zugangsdaten abfragen & testen ==="
read -r -p "API_KEY: " API_KEY
API_URL="https://allskykamera.space/getSecrets.php"

echo "> Teste API-Zugang..."
if ! RESPONSE=$(curl -s --fail "${API_URL}?key=${API_KEY}"); then
    echo "❌ API-URL oder Netzwerkfehler. Abbruch."
    exit 1
fi

# Auf Fehlerfeld prüfen
if echo "$RESPONSE" | grep -q '"error"'; then
    ERRMSG=$(echo "$RESPONSE" | sed -n 's/.*"error"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
    echo "❌ API-Fehler: ${ERRMSG:-unbekannt}. Abbruch."
    exit 1
fi

# Extrahiere influx_url und validiere
INFLUX_URL=$(echo "$RESPONSE" | jq -r '.influx_url // empty')
if [ -z "$INFLUX_URL" ]; then
    echo "❌ Ungültige API-Antwort: influx_url fehlt oder leer. Abbruch."
    exit 1
fi

# Extrahiere Kamera-ID und validiere
KAMERA_ID=$(echo "$RESPONSE" | jq -r '.kamera_id // empty')
if [ -z "$KAMERA_ID" ]; then
    echo "❌ Ungültige API-Antwort: kamera_id fehlt oder leer. Abbruch."
    exit 1
fi

echo "✅ API-Zugang validiert."
echo "→ Verbundene Kamera-ID: $KAMERA_ID"

# 1. Pfad zum Thomas Jaquin Interface abfragen
echo
echo "=== 1. Pfad zum Thomas-Jaquin-Interface ==="
read -r -p "Pfad zum Interface [default: /home/pi/allsky]: " ALLSKY_PATH
ALLSKY_PATH=${ALLSKY_PATH:-/home/pi/allsky}
echo "→ Interface-Pfad gesetzt auf: $ALLSKY_PATH"

# 2. System-Voraussetzungen
echo
echo "=== 2. System-Pakete installieren ==="
sudo apt-get update
sudo apt-get install -y \
    python3-pip python3-venv python3-smbus i2c-tools raspi-config \
    python3-psutil libatlas-base-dev libopenjp2-7 libtiff5 curl dos2unix jq

# 3. Schnittstellen aktivieren
echo
echo "=== 3. I²C, 1-Wire und Kamera aktivieren ==="
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_1wire 0
sudo raspi-config nonint do_camera 0

# 4. Python-Abhängigkeiten
echo
echo "=== 4. Python-Abhängigkeiten installieren ==="
pip3 install --user \
    influxdb-client adafruit-circuitpython-tsl2591 requests \
    pillow numpy matplotlib

# 5. askutils/ASKsecret.py anlegen
echo
echo "=== 5. askutils/ASKsecret.py anlegen ==="
cat > askutils/ASKsecret.py <<EOF
# Automatisch generierte Datei – nicht ins Repo committen!
API_KEY = "${API_KEY}"
API_URL = "${API_URL}"
EOF
echo "→ askutils/ASKsecret.py erstellt"

# 6. config.py erzeugen
echo
echo "=== 6. config.py anlegen ==="
read -r -p "KAMERA_NAME: " KAMERA_NAME
read -r -p "STANDORT_NAME: " STANDORT_NAME
read -r -p "BENUTZER_NAME: " BENUTZER_NAME
read -r -p "KONTAKT_EMAIL: " KONTAKT_EMAIL
read -r -p "LATITUDE: " LATITUDE
read -r -p "LONGITUDE: " LONGITUDE

read -r -p "IMAGE_BASE_PATH (z.B. images): " IMAGE_BASE_PATH
read -r -p "IMAGE_PATH (z.B. tmp): " IMAGE_PATH

read -r -p "PIX_SIZE_MM: " PIX_SIZE_MM
read -r -p "FOCAL_MM: " FOCAL_MM
read -r -p "ZP: " ZP
read -r -p "SQM_PATCH_SIZE: " SQM_PATCH_SIZE

read -r -p "BME280_ENABLED (True/False): " BME280_ENABLED
read -r -p "BME280_I2C_ADDRESS (hex, z.B. 0x76): " BME280_I2C_ADDRESS

read -r -p "TSL2591_ENABLED (True/False): " TSL2591_ENABLED
read -r -p "TSL2591_I2C_ADDRESS (hex, z.B. 0x29): " TSL2591_I2C_ADDRESS
read -r -p "TSL2591_SQM2_LIMIT: " TSL2591_SQM2_LIMIT
read -r -p "TSL2591_SQM_CORRECTION: " TSL2591_SQM_CORRECTION

read -r -p "DS18B20_ENABLED (True/False): " DS18B20_ENABLED

cat > config.py <<EOF
# Konfiguration der Kamera
# config.py

try:
    from askutils.ASKsecret import API_KEY, API_URL
except ImportError:
    print("❌ Datei 'ASKsecret.py' fehlt oder ist ungültig!")
    API_KEY = API_URL = None

####################################################################
# Benutzereinstellungen
####################################################################
KAMERA_ID     = "${KAMERA_ID}"
KAMERA_NAME   = "${KAMERA_NAME}"
STANDORT_NAME = "${STANDORT_NAME}"
BENUTZER_NAME = "${BENUTZER_NAME}"
KONTAKT_EMAIL = "${KONTAKT_EMAIL}"
LATITUDE      = ${LATITUDE}
LONGITUDE     = ${LONGITUDE}

####################################################################
# Pfade
####################################################################
ALLSKY_PATH     = "${ALLSKY_PATH}"
IMAGE_BASE_PATH = "${IMAGE_BASE_PATH}"
IMAGE_PATH      = "${IMAGE_PATH}"

####################################################################
# Kamera-Optik & SQM
####################################################################
PIX_SIZE_MM    = ${PIX_SIZE_MM}
FOCAL_MM       = ${FOCAL_MM}
ZP             = ${ZP}
SQM_PATCH_SIZE = ${SQM_PATCH_SIZE}

####################################################################
# Sensoren
####################################################################
BME280_ENABLED      = ${BME280_ENABLED}
BME280_I2C_ADDRESS  = ${BME280_I2C_ADDRESS}

TSL2591_ENABLED         = ${TSL2591_ENABLED}
TSL2591_I2C_ADDRESS     = ${TSL2591_I2C_ADDRESS}
TSL2591_SQM2_LIMIT      = ${TSL2591_SQM2_LIMIT}
TSL2591_SQM_CORRECTION  = ${TSL2591_SQM_CORRECTION}

DS18B20_ENABLED = ${DS18B20_ENABLED}

################### CRONTABS ###################################
CRONTABS = [
    {
        "comment": "Allsky Raspi-Status",
        "schedule": "*/1 * * * *",
        "command": "cd ${PROJECT_ROOT} && python3 -m scripts.raspi_status"
    },
    {
        "comment": "Config Update",
        "schedule": "0 12 * * *",
        "command": "cd ${PROJECT_ROOT} && python3 -m scripts.upload_config_json"
    },
    {
        "comment": "BME280 Sensor",
        "schedule": "*/1 * * * *",
        "command": "cd ${PROJECT_ROOT} && python3 -m scripts.bme280_logger"
    },
    {
        "comment": "TSL2591 Sensor",
        "schedule": "*/1 * * * *",
        "command": "cd ${PROJECT_ROOT} && python3 -m scripts.tsl2591_logger"
    },
    {
        "comment": "DS18B20 Sensor",
        "schedule": "*/1 * * * *",
        "command": "cd ${PROJECT_ROOT} && python3 -m scripts.ds18b20_logger"
    },
    {
        "comment": "Image FTP-Upload",
        "schedule": "*/2 * * * *",
        "command": "cd ${PROJECT_ROOT} && python3 -m scripts.run_image_upload"
    },
    {
        "comment": "Nightly FTP-Upload",
        "schedule": "30 7 * * *",
        "command": "cd ${PROJECT_ROOT} && python3 -m scripts.run_nightly_upload"
    },
    {
        "comment": "SQM Messung",
        "schedule": "*/5 * * * *",
        "command": "cd ${PROJECT_ROOT} && python3 -m scripts.sqm_camera_logger"
    },
    {
        "comment": "SQM Plot Generierung",
        "schedule": "0 8 * * *",
        "command": "cd ${PROJECT_ROOT} && python3 -m scripts.plot_sqm_night"
    }
]

###################################################################
# Nichts ändern !!!
###################################################################
FTP_VIDEO_DIR     = "videos"
FTP_KEOGRAM_DIR   = "keogram"
FTP_STARTRAIL_DIR = "startrails"
FTP_SQM_DIR       = "sqm"

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

echo "→ config.py erstellt"

# 7. FTP-Upload testen
echo
echo "=== 7. FTP-Upload testen ==="
python3 tests/ftp_upload_test.py

# 8. InfluxDB-Verbindung testen
echo
echo "=== 8. InfluxDB-Verbindung testen ==="
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${INFLUX_URL}/health")
if [ "$HTTP_CODE" != "200" ]; then
    echo "❌ InfluxDB-Erreichbarkeit fehlgeschlagen (HTTP $HTTP_CODE)"
    exit 1
fi
echo "✅ InfluxDB ist erreichbar."

echo
echo "✅ Installation und Konfiguration abgeschlossen!"
