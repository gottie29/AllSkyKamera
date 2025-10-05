#!/usr/bin/env bash
# Entfernt versehentliche CRLF-Zeilenenden bei Aufruf
if command -v dos2unix &>/dev/null; then
    dos2unix "$0" &>/dev/null || true
else
    sed -i 's/\r$//' "$0" || true
fi

set -euo pipefail
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
export PYTHONIOENCODING=UTF-8
export PYTHONUTF8=1

# Muss im Projekt-Root (mit askutils/) ausgeführt werden.
if [ ! -d "askutils" ]; then
    echo "❌ Dieses Skript muss im Projekt-Root (mit askutils/) aufgerufen werden."
    exit 1
fi

PROJECT_ROOT="$(pwd)"
echo "Arbeitsverzeichnis: $PROJECT_ROOT"

# Sofortige Prüfung: existiert bereits eine askutils/config.py?
if [ -f askutils/config.py ]; then
  read -r -p "askutils/config.py existiert bereits. Möchten Sie sie sichern und neu anlegen? (y/n): " OVERWRITE
  case "$OVERWRITE" in
    [Yy]* )
      mv askutils/config.py askutils/config.old.py
      echo "→ Alte config.py wurde in askutils/config.old.py umbenannt."
      ;;
    * )
      echo "→ Bestehende askutils/config.py bleibt erhalten. Installation abgebrochen."
      exit 0
      ;;
  esac
fi

# Schritt 0: API-Key
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

echo
echo "=== 0. API-Zugangsdaten abfragen & testen ==="
read -r -p "API_KEY: " API_KEY
ENC_API_URL="aHR0cHM6Ly9hbGxza3lrYW1lcmEuc3BhY2UvZ2V0U2VjcmV0cy5waHA="
API_URL=$(printf '%s' "$ENC_API_URL" | base64 -d)

echo "> Teste API-Zugang..."
if ! RESPONSE=$(curl -s --fail "${API_URL}?key=${API_KEY}"); then
    echo "❌ API-URL oder Netzwerkfehler. Abbruch."
    exit 1
fi

if echo "$RESPONSE" | grep -q '"error"'; then
    ERRMSG=$(echo "$RESPONSE" | sed -n 's/.*"error"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
    echo "❌ API-Fehler: ${ERRMSG:-unbekannt}. Abbruch."
    exit 1
fi

INFLUX_URL=$(echo "$RESPONSE" | sed -n 's/.*"influx_url"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
KAMERA_ID=$(echo "$RESPONSE" | sed -n 's/.*"kamera_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')

if [ -z "$INFLUX_URL" ] || [ -z "$KAMERA_ID" ]; then
    echo "❌ Ungültige API-Antwort. Abbruch."
    exit 1
fi

echo "✅ API-Zugang validiert."
echo "→ Verbundene Kamera-ID: $KAMERA_ID"

# Schritt 1: Pfad zum Thomas-Jaquin-Interface
echo
echo "=== 1. Pfad zum Thomas-Jaquin-Interface ==="
DEFAULT_ALLSKY_PATH="$HOME/allsky"
read -r -p "Pfad zum Interface [Default: $DEFAULT_ALLSKY_PATH]: " ALLSKY_PATH
ALLSKY_PATH=${ALLSKY_PATH:-$DEFAULT_ALLSKY_PATH}
echo "→ Interface-Pfad: $ALLSKY_PATH"

# Schritt 2: System-Pakete installieren
echo
echo "=== 2. System-Pakete installieren ==="
sudo apt-get update
sudo apt-get install -y \
    python3-pip python3-venv python3-smbus i2c-tools raspi-config \
    python3-psutil libatlas-base-dev python3-pil curl dos2unix

# Schritt 3: Schnittstellen aktivieren
echo
echo "=== 3. I²C, 1-Wire und Kamera aktivieren ==="
if sudo raspi-config nonint do_i2c 0 &>/dev/null; then
  echo "→ I²C aktiviert."
else
  echo "→ I²C übersprungen."
fi
if sudo raspi-config nonint do_1wire 0 &>/dev/null; then
  echo "→ 1-Wire aktiviert."
else
  echo "→ 1-Wire übersprungen."
fi
if sudo raspi-config nonint do_camera 0 &>/dev/null; then
  echo "→ Kamera aktiviert."
else
  echo "→ Kamera übersprungen."
fi

# Schritt 4: Python-Abhängigkeiten installieren
echo
echo "=== 4. Python-Abhängigkeiten installieren ==="
pip3 install --user \
    influxdb-client \
    adafruit-circuitpython-tsl2591 \
    requests \
    pillow \
    numpy \
    matplotlib \
    --break-system-packages

# Schritt 5: askutils/ASKsecret.py anlegen
echo
echo "=== 5. askutils/ASKsecret.py anlegen ==="
cat > askutils/ASKsecret.py <<EOF
import base64

# Automatisch generierte Datei – nicht ins Repo committen!
API_KEY = "${API_KEY}"
ENC_API_URL = "${ENC_API_URL}"
API_URL = base64.b64decode(ENC_API_URL).decode()
EOF
echo "→ askutils/ASKsecret.py erstellt"

# Schritt 6: askutils/config.py anlegen
echo
echo "=== 6. askutils/config.py anlegen ==="

# Kamera-Grunddaten
read -r -p "Name der Kamera (z.B. Meine AllskyCam): " KAMERA_NAME
read -r -p "Name des Standortes (z.B. Berliner Sternwarte): " STANDORT_NAME
read -r -p "Benutzername (z.B. Tom Mustermann): " BENUTZER_NAME
read -r -p "E-Mailadresse (optional): " KONTAKT_EMAIL
read -r -p "Webseite (optional): " WEBSITE

# Standortkoordinaten
read -r -p "Breitengrad des Standortes (z.B. 52.1253): " LATITUDE
read -r -p "Längengrad des Standortes (z.B. 13.1245): " LONGITUDE

# Image-Pfade (fest)
IMAGE_BASE_PATH="images"
IMAGE_PATH="tmp"
echo "→ IMAGE_BASE_PATH=$IMAGE_BASE_PATH, IMAGE_PATH=$IMAGE_PATH"

# Objektiv- & SQM-Daten
read -r -p "Pixelgröße des Kamerachips in mm (z.B. 0.00155): " PIX_SIZE_MM
read -r -p "Brennweite in mm (z.B. 1.85): " FOCAL_MM
read -r -p "Nullpunkt Helligkeit ZP (Default: 6.0): " ZP_INPUT
ZP=${ZP_INPUT:-6.0}
read -r -p "SQM-Patchgröße in Pixeln (z.B. 100): " SQM_PATCH_SIZE

# Sensorenauswahl mit Overlay-Abfrage
read -r -p "BME280 verwenden? (y/n): " USE_BME
if [[ "$USE_BME" =~ ^[Yy] ]]; then
  BME280_ENABLED=True
  read -r -p "I2C-Adresse BME280 (z.B. 0x76): " BME280_I2C_ADDRESS
  read -r -p "BME280_Overlay anlegen? (y/n): " BME280_OVERLAY_ANSWER
  BME280_OVERLAY=$([[ "$BME280_OVERLAY_ANSWER" =~ ^[Yy] ]] && echo True || echo False)
else
  BME280_ENABLED=False
  BME280_I2C_ADDRESS=0x00
  BME280_OVERLAY=False
fi

read -r -p "TSL2591 verwenden? (y/n): " USE_TSL
if [[ "$USE_TSL" =~ ^[Yy] ]]; then
  TSL2591_ENABLED=True
  read -r -p "I2C-Adresse TSL2591 (z.B. 0x29): " TSL2591_I2C_ADDRESS
  read -r -p "SQM2-Limit (z.B. 6.0): " TSL2591_SQM2_LIMIT
  read -r -p "SQM-Korrekturwert (z.B. 0.0): " TSL2591_SQM_CORRECTION
  read -r -p "TSL2591_Overlay anlegen? (y/n): " TSL2591_OVERLAY_ANSWER
  TSL2591_OVERLAY=$([[ "$TSL2591_OVERLAY_ANSWER" =~ ^[Yy] ]] && echo True || echo False)
else
  TSL2591_ENABLED=False
  TSL2591_I2C_ADDRESS=0x00
  TSL2591_SQM2_LIMIT=0.0
  TSL2591_SQM_CORRECTION=0.0
  TSL2591_OVERLAY=False
fi

read -r -p "DS18B20 verwenden? (y/n): " USE_DS
if [[ "$USE_DS" =~ ^[Yy] ]]; then
  DS18B20_ENABLED=True
  read -r -p "DS18B20_Overlay anlegen? (y/n): " DS18B20_OVERLAY_ANSWER
  DS18B20_OVERLAY=$([[ "$DS18B20_OVERLAY_ANSWER" =~ ^[Yy] ]] && echo True || echo False)
else
  DS18B20_ENABLED=False
  DS18B20_OVERLAY=False
fi

read -r -p "KP-Index als Overlay verwenden? (y/n): " USE_KP
if [[ "$USE_KP" =~ ^[Yy] ]]; then
  KPINDEX_OVERLAY=$([[ "$USE_KP" =~ ^[Yy] ]] && echo True || echo False)
else
  KPINDEX_OVERLAY=False
fi

read -r -p "Analemma generieren? (y/n): " USE_ANALEMMA
if [[ "$USE_ANALEMMA" =~ ^[Yy] ]]; then
  ANALEMMA_ENABLED=True
else
  ANALEMMA_ENABLED=False
fi

# CRONTAB-Blöcke vorbereiten
CRONTAB_BLOCKS=""

if [ "${BME280_ENABLED}" = "True" ]; then
CRONTAB_BLOCKS="$CRONTAB_BLOCKS
    {
        \"comment\": \"BME280 Sensor\",
        \"schedule\": \"*/1 * * * *\",
        \"command\": \"cd ${PROJECT_ROOT} && python3 -m scripts.bme280_logger\"
    },"
else
CRONTAB_BLOCKS="$CRONTAB_BLOCKS
    # BME280 deaktiviert"
fi

if [ "${TSL2591_ENABLED}" = "True" ]; then
CRONTAB_BLOCKS="$CRONTAB_BLOCKS
    {
        \"comment\": \"TSL2591 Sensor\",
        \"schedule\": \"*/1 * * * *\",
        \"command\": \"cd ${PROJECT_ROOT} && python3 -m scripts.tsl2591_logger\"
    },"
else
CRONTAB_BLOCKS="$CRONTAB_BLOCKS
    # TSL2591 deaktiviert"
fi

if [ "${DS18B20_ENABLED}" = "True" ]; then
CRONTAB_BLOCKS="$CRONTAB_BLOCKS
    {
        \"comment\": \"DS18B20 Sensor\",
        \"schedule\": \"*/1 * * * *\",
        \"command\": \"cd ${PROJECT_ROOT} && python3 -m scripts.ds18b20_logger\"
    },"
else
CRONTAB_BLOCKS="$CRONTAB_BLOCKS
    # DS18B20 deaktiviert"
fi

if [ "${KPINDEX_OVERLAY}" = "True" ]; then
CRONTAB_BLOCKS="$CRONTAB_BLOCKS
    {
        \"comment\": \"Generiere KPIndex Overlay variable\",
        \"schedule\": \"*/15 * * * *\",
        \"command\": \"cd ${PROJECT_ROOT} && python3 -m scripts.kpindex_logger\"
    },"
else
CRONTAB_BLOCKS="$CRONTAB_BLOCKS
    # KPIndex Overlay ist deaktiviert"
fi

if [ "${ANALEMMA_ENABLED}" = "True" ]; then
CRONTAB_BLOCKS="$CRONTAB_BLOCKS
    {
        \"comment\": \"Generiere Analemma\",
        \"schedule\": \"54/11 * * * *\",
        \"command\": \"cd ${PROJECT_ROOT} && python3 -m scripts.analemma\"
    },"
else
CRONTAB_BLOCKS="$CRONTAB_BLOCKS
    # Analemma ist deaktiviert"
fi

# write config.py
cat > askutils/config.py <<EOF
# config.py – automatisch generiert

try:
    from askutils.ASKsecret import API_KEY, API_URL
except ImportError:
    API_KEY = API_URL = None

# Kameradaten
KAMERA_ID      = "${KAMERA_ID}"
KAMERA_NAME    = "${KAMERA_NAME}"
STANDORT_NAME  = "${STANDORT_NAME}"
BENUTZER_NAME  = "${BENUTZER_NAME}"
KONTAKT_EMAIL  = "${KONTAKT_EMAIL}"
WEBSEITE       = "${WEBSITE}"

# Standortkoordinaten
LATITUDE       = ${LATITUDE}
LONGITUDE      = ${LONGITUDE}

# Pfade
ALLSKY_PATH     = "${ALLSKY_PATH}"
IMAGE_BASE_PATH = "${IMAGE_BASE_PATH}"
IMAGE_PATH      = "${IMAGE_PATH}"

# Objektiv- & SQM-Daten
PIX_SIZE_MM    = ${PIX_SIZE_MM}
FOCAL_MM       = ${FOCAL_MM}
ZP             = ${ZP}
SQM_PATCH_SIZE = ${SQM_PATCH_SIZE}

# Sensoren
BME280_ENABLED      = ${BME280_ENABLED}
BME280_I2C_ADDRESS  = ${BME280_I2C_ADDRESS}
BME280_OVERLAY      = ${BME280_OVERLAY}

TSL2591_ENABLED         = ${TSL2591_ENABLED}
TSL2591_I2C_ADDRESS     = ${TSL2591_I2C_ADDRESS}
TSL2591_SQM2_LIMIT      = ${TSL2591_SQM2_LIMIT}
TSL2591_SQM_CORRECTION  = ${TSL2591_SQM_CORRECTION}
TSL2591_OVERLAY         = ${TSL2591_OVERLAY}

DS18B20_ENABLED = ${DS18B20_ENABLED}
DS18B20_OVERLAY = ${DS18B20_OVERLAY}

KPINDEX_OVERLAY = ${KPINDEX_OVERLAY}

ANALEMMA_ENABLED = ${ANALEMMA_ENABLED}
KAMERA_WIDTH = 4056
KAMERA_HEIGHT = 3040
A_SHUTTER = 10       # 1 ms – deutlich kürzer!
A_GAIN = 1.0           # Kein Gain
A_BRIGHTNESS = 0.0
A_CONTRAST = 0.0
A_SATURATION = 0.0
A_PATH = "${PROJECT_ROOT}/tmp"

# CRONTABS
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
    },${CRONTAB_BLOCKS}
    {
        "comment": "Image FTP-Upload",
        "schedule": "*/2 * * * *",
        "command": "cd ${PROJECT_ROOT} && python3 -m scripts.run_image_upload"
    },
    {
        "comment": "Nightly FTP-Upload",
        "schedule": "45 8 * * *",
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
EOF

echo "→ askutils/config.py erstellt"

# Schritt 7: FTP-Upload testen
echo
echo "=== 7. FTP-Upload testen ==="
python3 tests/ftp_upload_test.py

# Schritt 8: InfluxDB-Verbindung testen
#echo
#echo "=== 8. InfluxDB-Verbindung testen ==="
#HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${INFLUX_URL}/health")
#if [ "$HTTP_CODE" != "200" ]; then
#    echo "❌ InfluxDB nicht erreichbar (HTTP $HTTP_CODE)"
#    exit 1
#fi
#echo "✅ InfluxDB ist erreichbar."

# Schritt 9: Crontabs eintragen
echo
echo "=== 9. Crontabs eintragen ==="
read -r -p "Sollen die Crontabs jetzt eingetragen werden? (y/n): " SET_CRON
if [[ "$SET_CRON" =~ ^[Yy] ]]; then
    echo "→ Trage Crontabs ein..."
    cd "$PROJECT_ROOT" && python3 -m scripts.manage_crontabs
fi

# Schritt 10: Uebertragung der config-Daten (config-json)
echo "→ Upload der config.json..."
cd "$PROJECT_ROOT" && python3 -m scripts.upload_config_json

echo
echo "✅ Installation und Konfiguration abgeschlossen!"
echo "✅ Ab sofort sollten alle Daten auf der Webseite erscheinen."
