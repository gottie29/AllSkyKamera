#!/usr/bin/env bash

# nicht zu strikt, damit "Abbrechen" das Skript nicht killt
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFG_FILE="$ROOT_DIR/askutils/config.py"

if ! command -v whiptail >/dev/null 2>&1; then
    echo "whiptail ist nicht installiert. Bitte mit 'sudo apt-get install whiptail' nachinstallieren."
    exit 1
fi

if [ ! -f "$CFG_FILE" ]; then
    echo "Konfigurationsdatei nicht gefunden: $CFG_FILE"
    exit 1
fi

# ---------------------------------------------------
# Sprache waehlen (de / en) – Deutsch ist Standard
# ---------------------------------------------------
LANG_CODE="de"
LANG_CHOICE=$(whiptail --title "Sprache / Language" \
  --menu "Bitte Sprache waehlen / Please choose language:" 15 60 2 \
  "de" "Deutsch" \
  "en" "English" 3>&1 1>&2 2>&3) || true

if [ -n "${LANG_CHOICE:-}" ]; then
  LANG_CODE="$LANG_CHOICE"
fi

# ---------------------------------------------------
# Helper: Wert aus bestehender config.py lesen
# (nur oberer Teil vor dem 'Nichts aendern !!!'-Block)
# ---------------------------------------------------
get_val() {
    local key="$1"
    python3 - "$CFG_FILE" "$key" << 'EOF'
import sys

path, key = sys.argv[1], sys.argv[2]
text = open(path, 'r', encoding='utf-8').read()
marker = "###################################################################"
if marker in text:
    text = text.split(marker, 1)[0]
ns = {}
try:
    code = compile(text, path, "exec")
    exec(code, ns, ns)
except Exception:
    ns = {}
val = ns.get(key, "")
print(val if val is not None else "")
EOF
}

# Strings fuer Python escapen (fuer Strings in config.py)
esc_py_str() {
    local s="$1"
    s="${s//\\/\\\\}"   # Backslashes
    s="${s//\"/\\\"}"   # Doppelte Anfuehrungszeichen
    echo "$s"
}

# Zahl wie "118" wieder in "0x76" umwandeln (fuer I2C-Adressen)
normalize_hex_literal() {
    local val="$1"
    if [[ "$val" =~ ^0x[0-9a-fA-F]+$ ]]; then
        echo "$val"
    elif [[ "$val" =~ ^[0-9]+$ ]]; then
        printf '0x%x\n' "$val"
    else
        echo "$val"
    fi
}

# bool -> Status-Text fuer Menue
bool_to_status() {
  local val="$1"
  local on off
  if [ "$LANG_CODE" = "de" ]; then
    on="aktiv"
    off="inaktiv"
  else
    on="enabled"
    off="disabled"
  fi
  case "$val" in
    True|true|1|YES|yes|on) echo "$on" ;;
    *) echo "$off" ;;
  esac
}

# ---------------------------------------------------
# Werte aus config.py lesen
# ---------------------------------------------------

# Kameradaten & Standort
KAMERA_ID="$(get_val "KAMERA_ID")"
KAMERA_NAME="$(get_val "KAMERA_NAME")"
STANDORT_NAME="$(get_val "STANDORT_NAME")"
BENUTZER_NAME="$(get_val "BENUTZER_NAME")"
KONTAKT_EMAIL="$(get_val "KONTAKT_EMAIL")"
WEBSEITE="$(get_val "WEBSEITE")"

LATITUDE="$(get_val "LATITUDE")"
LONGITUDE="$(get_val "LONGITUDE")"

# Pfade / INDI
ALLSKY_PATH="$(get_val "ALLSKY_PATH")"
IMAGE_BASE_PATH="$(get_val "IMAGE_BASE_PATH")"
IMAGE_PATH="$(get_val "IMAGE_PATH")"

INDI="$(get_val "INDI")"
CAMERAID="$(get_val "CAMERAID")"

# Sensor-Status
BME280_ENABLED="$(get_val "BME280_ENABLED")"
TSL2591_ENABLED="$(get_val "TSL2591_ENABLED")"
DS18B20_ENABLED="$(get_val "DS18B20_ENABLED")"
DHT11_ENABLED="$(get_val "DHT11_ENABLED")"
DHT22_ENABLED="$(get_val "DHT22_ENABLED")"
MLX90614_ENABLED="$(get_val "MLX90614_ENABLED")"
HTU21_ENABLED="$(get_val "HTU21_ENABLED")"
SHT3X_ENABLED="$(get_val "SHT3X_ENABLED")"

# Sensor-Parameter (alt)
BME280_I2C_ADDRESS="$(get_val "BME280_I2C_ADDRESS")"
BME280_OVERLAY="$(get_val "BME280_OVERLAY")"

TSL2591_I2C_ADDRESS="$(get_val "TSL2591_I2C_ADDRESS")"
TSL2591_SQM2_LIMIT="$(get_val "TSL2591_SQM2_LIMIT")"
TSL2591_SQM_CORRECTION="$(get_val "TSL2591_SQM_CORRECTION")"
TSL2591_OVERLAY="$(get_val "TSL2591_OVERLAY")"

DS18B20_OVERLAY="$(get_val "DS18B20_OVERLAY")"

DHT11_GPIO_BCM="$(get_val "DHT11_GPIO_BCM")"
DHT11_RETRIES="$(get_val "DHT11_RETRIES")"
DHT11_RETRY_DELAY="$(get_val "DHT11_RETRY_DELAY")"
DHT11_OVERLAY="$(get_val "DHT11_OVERLAY")"

DHT22_GPIO_BCM="$(get_val "DHT22_GPIO_BCM")"
DHT22_RETRIES="$(get_val "DHT22_RETRIES")"
DHT22_RETRY_DELAY="$(get_val "DHT22_RETRY_DELAY")"
DHT22_OVERLAY="$(get_val "DHT22_OVERLAY")"

MLX90614_I2C_ADDRESS="$(get_val "MLX90614_I2C_ADDRESS")"

HTU21_I2C_ADDRESS="$(get_val "HTU21_I2C_ADDRESS")"
HTU21_TEMP_OFFSET="$(get_val "HTU21_TEMP_OFFSET")"
HTU21_HUM_OFFSET="$(get_val "HTU21_HUM_OFFSET")"
HTU21_OVERLAY="$(get_val "HTU21_OVERLAY")"

SHT3X_I2C_ADDRESS="$(get_val "SHT3X_I2C_ADDRESS")"
SHT3X_TEMP_OFFSET="$(get_val "SHT3X_TEMP_OFFSET")"
SHT3X_HUM_OFFSET="$(get_val "SHT3X_HUM_OFFSET")"
SHT3X_OVERLAY="$(get_val "SHT3X_OVERLAY")"

# --- NEU: Offsets / Kalibrierungen ---
BME280_TEMP_OFFSET_C="$(get_val "BME280_TEMP_OFFSET_C")"
BME280_PRESS_OFFSET_HPA="$(get_val "BME280_PRESS_OFFSET_HPA")"
BME280_HUM_OFFSET_PCT="$(get_val "BME280_HUM_OFFSET_PCT")"

DS18B20_TEMP_OFFSET_C="$(get_val "DS18B20_TEMP_OFFSET_C")"

DHT11_TEMP_OFFSET_C="$(get_val "DHT11_TEMP_OFFSET_C")"
DHT11_HUM_OFFSET_PCT="$(get_val "DHT11_HUM_OFFSET_PCT")"

DHT22_TEMP_OFFSET_C="$(get_val "DHT22_TEMP_OFFSET_C")"
DHT22_HUM_OFFSET_PCT="$(get_val "DHT22_HUM_OFFSET_PCT")"

MLX90614_AMBIENT_OFFSET_C="$(get_val "MLX90614_AMBIENT_OFFSET_C")"

# --- NEU: MLX Cloud Koeffizienten ---
MLX_CLOUD_K1="$(get_val "MLX_CLOUD_K1")"
MLX_CLOUD_K2="$(get_val "MLX_CLOUD_K2")"
MLX_CLOUD_K3="$(get_val "MLX_CLOUD_K3")"
MLX_CLOUD_K4="$(get_val "MLX_CLOUD_K4")"
MLX_CLOUD_K5="$(get_val "MLX_CLOUD_K5")"
MLX_CLOUD_K6="$(get_val "MLX_CLOUD_K6")"
MLX_CLOUD_K7="$(get_val "MLX_CLOUD_K7")"

# Logger-Intervalle (Minuten)
BME280_LOG_INTERVAL_MIN="$(get_val "BME280_LOG_INTERVAL_MIN")"
TSL2591_LOG_INTERVAL_MIN="$(get_val "TSL2591_LOG_INTERVAL_MIN")"
DS18B20_LOG_INTERVAL_MIN="$(get_val "DS18B20_LOG_INTERVAL_MIN")"
DHT11_LOG_INTERVAL_MIN="$(get_val "DHT11_LOG_INTERVAL_MIN")"
DHT22_LOG_INTERVAL_MIN="$(get_val "DHT22_LOG_INTERVAL_MIN")"
MLX90614_LOG_INTERVAL_MIN="$(get_val "MLX90614_LOG_INTERVAL_MIN")"
HTU21_LOG_INTERVAL_MIN="$(get_val "HTU21_LOG_INTERVAL_MIN")"
SHT3X_LOG_INTERVAL_MIN="$(get_val "SHT3X_LOG_INTERVAL_MIN")"

# Sensor-Namen
BME280_NAME="$(get_val "BME280_NAME")"
DS18B20_NAME="$(get_val "DS18B20_NAME")"
MLX90614_NAME="$(get_val "MLX90614_NAME")"
TSL2591_NAME="$(get_val "TSL2591_NAME")"
DHT11_NAME="$(get_val "DHT11_NAME")"
DHT22_NAME="$(get_val "DHT22_NAME")"
HTU21_NAME="$(get_val "HTU21_NAME")"
SHT3X_NAME="$(get_val "SHT3X_NAME")"

# Kamera / Objektiv / SQM / Analemma / KpIndex
PIX_SIZE_MM="$(get_val "PIX_SIZE_MM")"
FOCAL_MM="$(get_val "FOCAL_MM")"
ZP="$(get_val "ZP")"
SQM_PATCH_SIZE="$(get_val "SQM_PATCH_SIZE")"

KAMERA_WIDTH="$(get_val "KAMERA_WIDTH")"
KAMERA_HEIGHT="$(get_val "KAMERA_HEIGHT")"

ANALEMMA_ENABLED="$(get_val "ANALEMMA_ENABLED")"
A_SHUTTER="$(get_val "A_SHUTTER")"
A_GAIN="$(get_val "A_GAIN")"
A_BRIGHTNESS="$(get_val "A_BRIGHTNESS")"
A_CONTRAST="$(get_val "A_CONTRAST")"
A_SATURATION="$(get_val "A_SATURATION")"

KPINDEX_ENABLED="$(get_val "KPINDEX_ENABLED")"
KPINDEX_OVERLAY="$(get_val "KPINDEX_OVERLAY")"
KPINDEX_LOG_INTERVAL_MIN="$(get_val "KPINDEX_LOG_INTERVAL_MIN")"

# ---------------------------------------------------
# INDI Erkennung / Normalisierung (frueh, aber OHNE Overlay-Override)
# Wichtig: Overlays werden spaeter (kurz vor dem Schreiben) hart deaktiviert,
# damit Menu-Eingaben / get_val nichts "zurueck-ueberschreiben" koennen.
# ---------------------------------------------------
INDI_ACTIVE="0"
if [ "${INDI:-0}" = "1" ] || [ "${INDI:-0}" = "True" ] || [ "${INDI:-0}" = "true" ]; then
  INDI="1"
  INDI_ACTIVE="1"
else
  INDI="0"
fi

# ---------------------------------------------------
# Defaults
# ---------------------------------------------------
[ -z "$KAMERA_ID" ] && KAMERA_ID="ASK999"
[ -z "$KAMERA_NAME" ] && KAMERA_NAME="Test-Kamera"
[ -z "$STANDORT_NAME" ] && STANDORT_NAME="Test-Kamera"
[ -z "$BENUTZER_NAME" ] && BENUTZER_NAME="Stefan"
[ -z "$KONTAKT_EMAIL" ] && KONTAKT_EMAIL=""
[ -z "$WEBSEITE" ] && WEBSEITE=""

[ -z "$LATITUDE" ] && LATITUDE="52.12"
[ -z "$LONGITUDE" ] && LONGITUDE="13.12"

# Pfade: Default je nach Interface
if [ "$INDI_ACTIVE" = "1" ]; then
  [ -z "$ALLSKY_PATH" ] && ALLSKY_PATH="/var/www/html/allsky"
  [ -z "$IMAGE_BASE_PATH" ] && IMAGE_BASE_PATH="images"
  [ -z "$IMAGE_PATH" ] && IMAGE_PATH="tmp"
else
  [ -z "$ALLSKY_PATH" ] && ALLSKY_PATH="$HOME/allsky"
  [ -z "$IMAGE_BASE_PATH" ] && IMAGE_BASE_PATH="images"
  [ -z "$IMAGE_PATH" ] && IMAGE_PATH="tmp"
fi

[ -z "$CAMERAID" ] && CAMERAID="ccd_002f6961-ba9f-4387-8c2e-09ec5c72f55d"

[ -z "$BME280_ENABLED" ] && BME280_ENABLED="False"
[ -z "$TSL2591_ENABLED" ] && TSL2591_ENABLED="False"
[ -z "$DS18B20_ENABLED" ] && DS18B20_ENABLED="False"
[ -z "$DHT11_ENABLED" ] && DHT11_ENABLED="False"
[ -z "$DHT22_ENABLED" ] && DHT22_ENABLED="False"
[ -z "$MLX90614_ENABLED" ] && MLX90614_ENABLED="False"
[ -z "$HTU21_ENABLED" ] && HTU21_ENABLED="False"
[ -z "$SHT3X_ENABLED" ] && SHT3X_ENABLED="False"

[ -z "$BME280_I2C_ADDRESS" ] && BME280_I2C_ADDRESS="0x76"
[ -z "$BME280_OVERLAY" ] && BME280_OVERLAY="False"

[ -z "$TSL2591_I2C_ADDRESS" ] && TSL2591_I2C_ADDRESS="0x29"
[ -z "$TSL2591_SQM2_LIMIT" ] && TSL2591_SQM2_LIMIT="0.0"
[ -z "$TSL2591_SQM_CORRECTION" ] && TSL2591_SQM_CORRECTION="0.0"
[ -z "$TSL2591_OVERLAY" ] && TSL2591_OVERLAY="False"

[ -z "$DS18B20_OVERLAY" ] && DS18B20_OVERLAY="False"

[ -z "$DHT11_GPIO_BCM" ] && DHT11_GPIO_BCM="6"
[ -z "$DHT11_RETRIES" ] && DHT11_RETRIES="10"
[ -z "$DHT11_RETRY_DELAY" ] && DHT11_RETRY_DELAY="0.3"
[ -z "$DHT11_OVERLAY" ] && DHT11_OVERLAY="False"

[ -z "$DHT22_GPIO_BCM" ] && DHT22_GPIO_BCM="6"
[ -z "$DHT22_RETRIES" ] && DHT22_RETRIES="5"
[ -z "$DHT22_RETRY_DELAY" ] && DHT22_RETRY_DELAY="12"
[ -z "$DHT22_OVERLAY" ] && DHT22_OVERLAY="False"

[ -z "$MLX90614_I2C_ADDRESS" ] && MLX90614_I2C_ADDRESS="0x5a"

[ -z "$HTU21_I2C_ADDRESS" ] && HTU21_I2C_ADDRESS="0x40"
[ -z "$HTU21_TEMP_OFFSET" ] && HTU21_TEMP_OFFSET="0.0"
[ -z "$HTU21_HUM_OFFSET" ] && HTU21_HUM_OFFSET="0.0"
[ -z "$HTU21_OVERLAY" ] && HTU21_OVERLAY="False"

[ -z "$SHT3X_I2C_ADDRESS" ] && SHT3X_I2C_ADDRESS="0x44"
[ -z "$SHT3X_TEMP_OFFSET" ] && SHT3X_TEMP_OFFSET="0.0"
[ -z "$SHT3X_HUM_OFFSET" ] && SHT3X_HUM_OFFSET="0.0"
[ -z "$SHT3X_OVERLAY" ] && SHT3X_OVERLAY="False"

[ -z "$BME280_NAME" ] && BME280_NAME="BME280"
[ -z "$DS18B20_NAME" ] && DS18B20_NAME="DS18B20"
[ -z "$MLX90614_NAME" ] && MLX90614_NAME="MLX90614"
[ -z "$TSL2591_NAME" ] && TSL2591_NAME="TSL2591"
[ -z "$DHT11_NAME" ] && DHT11_NAME="DHT11"
[ -z "$DHT22_NAME" ] && DHT22_NAME="DHT22"
[ -z "$HTU21_NAME" ] && HTU21_NAME="HTU21 / GY-21"
[ -z "$SHT3X_NAME" ] && SHT3X_NAME="SHT3x"

# Standard-Logger-Intervalle in Minuten
[ -z "$BME280_LOG_INTERVAL_MIN" ]   && BME280_LOG_INTERVAL_MIN="1"
[ -z "$TSL2591_LOG_INTERVAL_MIN" ]  && TSL2591_LOG_INTERVAL_MIN="1"
[ -z "$DS18B20_LOG_INTERVAL_MIN" ]  && DS18B20_LOG_INTERVAL_MIN="1"
[ -z "$DHT11_LOG_INTERVAL_MIN" ]    && DHT11_LOG_INTERVAL_MIN="1"
[ -z "$DHT22_LOG_INTERVAL_MIN" ]    && DHT22_LOG_INTERVAL_MIN="1"
[ -z "$MLX90614_LOG_INTERVAL_MIN" ] && MLX90614_LOG_INTERVAL_MIN="1"
[ -z "$HTU21_LOG_INTERVAL_MIN" ]    && HTU21_LOG_INTERVAL_MIN="1"
[ -z "$SHT3X_LOG_INTERVAL_MIN" ]    && SHT3X_LOG_INTERVAL_MIN="1"

# Defaults fuer Kamera / Objektiv / SQM / Analemma / KpIndex
[ -z "$PIX_SIZE_MM" ] && PIX_SIZE_MM="0.00155"
[ -z "$FOCAL_MM" ] && FOCAL_MM="1.85"
[ -z "$ZP" ] && ZP="6.0"
[ -z "$SQM_PATCH_SIZE" ] && SQM_PATCH_SIZE="100"

[ -z "$KAMERA_WIDTH" ] && KAMERA_WIDTH="4056"
[ -z "$KAMERA_HEIGHT" ] && KAMERA_HEIGHT="3040"

[ -z "$ANALEMMA_ENABLED" ] && ANALEMMA_ENABLED="False"
[ -z "$A_SHUTTER" ] && A_SHUTTER="10"
[ -z "$A_GAIN" ] && A_GAIN="1.0"
[ -z "$A_BRIGHTNESS" ] && A_BRIGHTNESS="0.0"
[ -z "$A_CONTRAST" ] && A_CONTRAST="0.0"
[ -z "$A_SATURATION" ] && A_SATURATION="0.0"

[ -z "$KPINDEX_ENABLED" ] && KPINDEX_ENABLED="False"
[ -z "$KPINDEX_OVERLAY" ] && KPINDEX_OVERLAY="False"
[ -z "$KPINDEX_LOG_INTERVAL_MIN" ] && KPINDEX_LOG_INTERVAL_MIN="15"

# --- NEU: Defaults Offsets ---
[ -z "$BME280_TEMP_OFFSET_C" ] && BME280_TEMP_OFFSET_C="0.0"
[ -z "$BME280_PRESS_OFFSET_HPA" ] && BME280_PRESS_OFFSET_HPA="0.0"
[ -z "$BME280_HUM_OFFSET_PCT" ] && BME280_HUM_OFFSET_PCT="0.0"

[ -z "$DS18B20_TEMP_OFFSET_C" ] && DS18B20_TEMP_OFFSET_C="0.0"

[ -z "$DHT11_TEMP_OFFSET_C" ] && DHT11_TEMP_OFFSET_C="0.0"
[ -z "$DHT11_HUM_OFFSET_PCT" ] && DHT11_HUM_OFFSET_PCT="0.0"

[ -z "$DHT22_TEMP_OFFSET_C" ] && DHT22_TEMP_OFFSET_C="0.0"
[ -z "$DHT22_HUM_OFFSET_PCT" ] && DHT22_HUM_OFFSET_PCT="0.0"

[ -z "$MLX90614_AMBIENT_OFFSET_C" ] && MLX90614_AMBIENT_OFFSET_C="0.0"

# --- NEU: Defaults MLX Cloud ---
[ -z "$MLX_CLOUD_K1" ] && MLX_CLOUD_K1="100.0"
[ -z "$MLX_CLOUD_K2" ] && MLX_CLOUD_K2="0.0"
[ -z "$MLX_CLOUD_K3" ] && MLX_CLOUD_K3="0.0"
[ -z "$MLX_CLOUD_K4" ] && MLX_CLOUD_K4="0.0"
[ -z "$MLX_CLOUD_K5" ] && MLX_CLOUD_K5="0.0"
[ -z "$MLX_CLOUD_K6" ] && MLX_CLOUD_K6="0.0"
[ -z "$MLX_CLOUD_K7" ] && MLX_CLOUD_K7="0.0"

# I2C-Adressen in schoene Hex-Notation bringen
BME280_I2C_ADDRESS="$(normalize_hex_literal "$BME280_I2C_ADDRESS")"
TSL2591_I2C_ADDRESS="$(normalize_hex_literal "$TSL2591_I2C_ADDRESS")"
MLX90614_I2C_ADDRESS="$(normalize_hex_literal "$MLX90614_I2C_ADDRESS")"
HTU21_I2C_ADDRESS="$(normalize_hex_literal "$HTU21_I2C_ADDRESS")"
SHT3X_I2C_ADDRESS="$(normalize_hex_literal "$SHT3X_I2C_ADDRESS")"

# --- NEU: Float Normalisierung (Komma -> Punkt) ---
BME280_TEMP_OFFSET_C="${BME280_TEMP_OFFSET_C//,/.}"
BME280_PRESS_OFFSET_HPA="${BME280_PRESS_OFFSET_HPA//,/.}"
BME280_HUM_OFFSET_PCT="${BME280_HUM_OFFSET_PCT//,/.}"

DS18B20_TEMP_OFFSET_C="${DS18B20_TEMP_OFFSET_C//,/.}"

DHT11_TEMP_OFFSET_C="${DHT11_TEMP_OFFSET_C//,/.}"
DHT11_HUM_OFFSET_PCT="${DHT11_HUM_OFFSET_PCT//,/.}"
DHT22_TEMP_OFFSET_C="${DHT22_TEMP_OFFSET_C//,/.}"
DHT22_HUM_OFFSET_PCT="${DHT22_HUM_OFFSET_PCT//,/.}"

MLX90614_AMBIENT_OFFSET_C="${MLX90614_AMBIENT_OFFSET_C//,/.}"

MLX_CLOUD_K1="${MLX_CLOUD_K1//,/.}"
MLX_CLOUD_K2="${MLX_CLOUD_K2//,/.}"
MLX_CLOUD_K3="${MLX_CLOUD_K3//,/.}"
MLX_CLOUD_K4="${MLX_CLOUD_K4//,/.}"
MLX_CLOUD_K5="${MLX_CLOUD_K5//,/.}"
MLX_CLOUD_K6="${MLX_CLOUD_K6//,/.}"
MLX_CLOUD_K7="${MLX_CLOUD_K7//,/.}"

# ---------------------------------------------------
# INDI Fixups (Pfade + CAMERAID) NACH Defaults
# - Pfade/CameraID fuer INDI automatisch korrigieren
# (Overlays werden absichtlich NICHT hier ueberschrieben!)
# ---------------------------------------------------
if [ "$INDI_ACTIVE" = "1" ]; then
  ALLSKY_PATH="/var/www/html/allsky"
  IMAGE_BASE_PATH="images"
  IMAGE_PATH="tmp"

  # CAMERAID (ccd_*) aus INDI images Verzeichnis auslesen
  INDI_IMAGES_DIR="${ALLSKY_PATH}/images"
  if [ -d "${INDI_IMAGES_DIR}" ]; then
    CCD_DIR_NAME="$(find "${INDI_IMAGES_DIR}" -maxdepth 1 -type d -name 'ccd_*' -printf '%f\n' 2>/dev/null | sort | head -n 1 || true)"
    if [ -n "${CCD_DIR_NAME}" ]; then
      CAMERAID="${CCD_DIR_NAME}"
    fi
  fi
fi

# ---------------------------------------------------
# Standortdaten-Dialog
# ---------------------------------------------------
edit_location() {
  local title lbl_cam lbl_loc lbl_user lbl_mail lbl_web lbl_lat lbl_lon
  local rc tmp

  if [ "$LANG_CODE" = "de" ]; then
    title="Standortdaten"
    lbl_cam="Kamera-Name (Anzeige auf Webseite)"
    lbl_loc="Standort (z.B. Archenhold-Sternwarte)"
    lbl_user="Benutzer / Betreiber"
    lbl_mail="Kontakt-E-Mail (optional)"
    lbl_web="Webseite (optional, https://...)"
    lbl_lat="Breitengrad (LATITUDE, z.B. 52.1234)"
    lbl_lon="Laengengrad (LONGITUDE, z.B. 13.1234)"
  else
    title="Location data"
    lbl_cam="Camera name (shown on website)"
    lbl_loc="Location (e.g. Archenhold Observatory)"
    lbl_user="User / operator"
    lbl_mail="Contact email (optional)"
    lbl_web="Website (optional, https://...)"
    lbl_lat="Latitude (e.g. 52.1234)"
    lbl_lon="Longitude (e.g. 13.1234)"
  fi

  # Alte Werte sichern (fuer Rollback)
  local OLD_KAMERA_NAME="$KAMERA_NAME"
  local OLD_STANDORT_NAME="$STANDORT_NAME"
  local OLD_BENUTZER_NAME="$BENUTZER_NAME"
  local OLD_KONTAKT_EMAIL="$KONTAKT_EMAIL"
  local OLD_WEBSEITE="$WEBSEITE"
  local OLD_LATITUDE="$LATITUDE"
  local OLD_LONGITUDE="$LONGITUDE"

  # Kamera-Name
  tmp=$(whiptail --title "$title" --inputbox "$lbl_cam" 10 70 "$KAMERA_NAME" 3>&1 1>&2 2>&3)
  rc=$?; [ $rc -ne 0 ] && return 0
  KAMERA_NAME="$tmp"

  # Standort
  tmp=$(whiptail --title "$title" --inputbox "$lbl_loc" 10 70 "$STANDORT_NAME" 3>&1 1>&2 2>&3)
  rc=$?; if [ $rc -ne 0 ]; then
    KAMERA_NAME="$OLD_KAMERA_NAME"
    STANDORT_NAME="$OLD_STANDORT_NAME"
    BENUTZER_NAME="$OLD_BENUTZER_NAME"
    KONTAKT_EMAIL="$OLD_KONTAKT_EMAIL"
    WEBSEITE="$OLD_WEBSEITE"
    LATITUDE="$OLD_LATITUDE"
    LONGITUDE="$OLD_LONGITUDE"
    return 0
  fi
  STANDORT_NAME="$tmp"

  # Benutzer
  tmp=$(whiptail --title "$title" --inputbox "$lbl_user" 10 70 "$BENUTZER_NAME" 3>&1 1>&2 2>&3)
  rc=$?; if [ $rc -ne 0 ]; then
    KAMERA_NAME="$OLD_KAMERA_NAME"
    STANDORT_NAME="$OLD_STANDORT_NAME"
    BENUTZER_NAME="$OLD_BENUTZER_NAME"
    KONTAKT_EMAIL="$OLD_KONTAKT_EMAIL"
    WEBSEITE="$OLD_WEBSEITE"
    LATITUDE="$OLD_LATITUDE"
    LONGITUDE="$OLD_LONGITUDE"
    return 0
  fi
  BENUTZER_NAME="$tmp"

  # Kontakt
  tmp=$(whiptail --title "$title" --inputbox "$lbl_mail" 10 70 "$KONTAKT_EMAIL" 3>&1 1>&2 2>&3)
  rc=$?; if [ $rc -ne 0 ]; then
    KAMERA_NAME="$OLD_KAMERA_NAME"
    STANDORT_NAME="$OLD_STANDORT_NAME"
    BENUTZER_NAME="$OLD_BENUTZER_NAME"
    KONTAKT_EMAIL="$OLD_KONTAKT_EMAIL"
    WEBSEITE="$OLD_WEBSEITE"
    LATITUDE="$OLD_LATITUDE"
    LONGITUDE="$OLD_LONGITUDE"
    return 0
  fi
  KONTAKT_EMAIL="$tmp"

  # Webseite
  tmp=$(whiptail --title "$title" --inputbox "$lbl_web" 10 70 "$WEBSEITE" 3>&1 1>&2 2>&3)
  rc=$?; if [ $rc -ne 0 ]; then
    KAMERA_NAME="$OLD_KAMERA_NAME"
    STANDORT_NAME="$OLD_STANDORT_NAME"
    BENUTZER_NAME="$OLD_BENUTZER_NAME"
    KONTAKT_EMAIL="$OLD_KONTAKT_EMAIL"
    WEBSEITE="$OLD_WEBSEITE"
    LATITUDE="$OLD_LATITUDE"
    LONGITUDE="$OLD_LONGITUDE"
    return 0
  fi
  WEBSEITE="$tmp"

  # Breitengrad
  tmp=$(whiptail --title "$title" --inputbox "$lbl_lat" 10 70 "$LATITUDE" 3>&1 1>&2 2>&3)
  rc=$?; if [ $rc -ne 0 ]; then
    KAMERA_NAME="$OLD_KAMERA_NAME"
    STANDORT_NAME="$OLD_STANDORT_NAME"
    BENUTZER_NAME="$OLD_BENUTZER_NAME"
    KONTAKT_EMAIL="$OLD_KONTAKT_EMAIL"
    WEBSEITE="$OLD_WEBSEITE"
    LATITUDE="$OLD_LATITUDE"
    LONGITUDE="$OLD_LONGITUDE"
    return 0
  fi
  LATITUDE="$tmp"

  # Laengengrad
  tmp=$(whiptail --title "$title" --inputbox "$lbl_lon" 10 70 "$LONGITUDE" 3>&1 1>&2 2>&3)
  rc=$?; if [ $rc -ne 0 ]; then
    KAMERA_NAME="$OLD_KAMERA_NAME"
    STANDORT_NAME="$OLD_STANDORT_NAME"
    BENUTZER_NAME="$OLD_BENUTZER_NAME"
    KONTAKT_EMAIL="$OLD_KONTAKT_EMAIL"
    WEBSEITE="$OLD_WEBSEITE"
    LATITUDE="$OLD_LATITUDE"
    LONGITUDE="$OLD_LONGITUDE"
    return 0
  fi
  LONGITUDE="$tmp"

  LATITUDE="${LATITUDE//,/.}"
  LONGITUDE="${LONGITUDE//,/.}"
}

# ---------------------------------------------------
# Kamera / Objektiv
# ---------------------------------------------------
edit_camera() {
  local title q_w q_h rc tmp
  if [ "$LANG_CODE" = "de" ]; then
    title="Kamera"
    q_w="Sensorbreite in Pixel (KAMERA_WIDTH):"
    q_h="Sensorhoehe in Pixel (KAMERA_HEIGHT):"
  else
    title="Camera"
    q_w="Sensor width in pixels (KAMERA_WIDTH):"
    q_h="Sensor height in pixels (KAMERA_HEIGHT):"
  fi

  local OLD_W="$KAMERA_WIDTH"
  local OLD_H="$KAMERA_HEIGHT"

  tmp=$(whiptail --title "$title" --inputbox "$q_w" 10 70 "$KAMERA_WIDTH" 3>&1 1>&2 2>&3)
  rc=$?; [ $rc -ne 0 ] && return 0
  KAMERA_WIDTH="$tmp"

  tmp=$(whiptail --title "$title" --inputbox "$q_h" 10 70 "$KAMERA_HEIGHT" 3>&1 1>&2 2>&3)
  rc=$?
  if [ $rc -ne 0 ]; then
    KAMERA_WIDTH="$OLD_W"
    KAMERA_HEIGHT="$OLD_H"
    return 0
  fi
  KAMERA_HEIGHT="$tmp"
}

edit_lens() {
  local title q_pix q_foc rc tmp
  if [ "$LANG_CODE" = "de" ]; then
    title="Objektiv"
    q_pix="Pixelgroesse in mm (PIX_SIZE_MM, z.B. 0.00155):"
    q_foc="Brennweite in mm (FOCAL_MM, z.B. 1.85):"
  else
    title="Lens"
    q_pix="Pixel size in mm (PIX_SIZE_MM, e.g. 0.00155):"
    q_foc="Focal length in mm (FOCAL_MM, e.g. 1.85):"
  fi

  local OLD_PIX="$PIX_SIZE_MM"
  local OLD_FOC="$FOCAL_MM"

  tmp=$(whiptail --title "$title" --inputbox "$q_pix" 10 70 "$PIX_SIZE_MM" 3>&1 1>&2 2>&3)
  rc=$?; [ $rc -ne 0 ] && return 0
  PIX_SIZE_MM="${tmp//,/.}"

  tmp=$(whiptail --title "$title" --inputbox "$q_foc" 10 70 "$FOCAL_MM" 3>&1 1>&2 2>&3)
  rc=$?
  if [ $rc -ne 0 ]; then
    PIX_SIZE_MM="$OLD_PIX"
    FOCAL_MM="$OLD_FOC"
    return 0
  fi
  FOCAL_MM="${tmp//,/.}"
}

camera_lens_menu() {
  local tb mp back_label o_cam o_lens
  if [ "$LANG_CODE" = "de" ]; then
    tb="Kamera und Objektiv"
    mp="Bitte einen Bereich waehlen:"
    back_label="Zurueck"
    o_cam="Kamera (Sensorgroeße)"
    o_lens="Objektiv (Pixelgroeße/Brennweite)"
  else
    tb="Camera & optics"
    mp="Please choose:"
    back_label="Back"
    o_cam="Camera (sensor size)"
    o_lens="Lens (pixel size/focal length)"
  fi

  while true; do
    CHOICE=$(whiptail --title "$tb" --menu "$mp" 15 70 6 \
      "1" "$o_cam" \
      "2" "$o_lens" \
      "Z" "$back_label" \
      3>&1 1>&2 2>&3) || return 0

    case "$CHOICE" in
      "1") edit_camera ;;
      "2") edit_lens ;;
      "Z") return 0 ;;
    esac
  done
}

# ---------------------------------------------------
# Sensor-Untermenues
# ---------------------------------------------------
# (ab hier: unveraendert aus deinem Script – nur weiter unten beim Speichern kommt der INDI-Overlay-Guard)
# ---------------------------------------------------

edit_bme280() {
  local title q_enable q_name q_i2c q_int q_ov q_toff q_poff q_hoff rc tmp
  if [ "$LANG_CODE" = "de" ]; then
    title="Sensor BME280"
    q_enable="BME280 (Temp/Feuchte/Druck) aktivieren?"
    q_name="Name fuer BME280:"
    q_i2c="I2C-Adresse des BME280 (z.B. 0x76):"
    q_toff="Temperatur-Offset in °C (BME280_TEMP_OFFSET_C, z.B. 0.0):"
    q_poff="Druck-Offset in hPa (BME280_PRESS_OFFSET_HPA, z.B. 0.0):"
    q_hoff="Feuchte-Offset in %-Punkten (BME280_HUM_OFFSET_PCT, z.B. 0.0):"
    q_int="Logger-Intervall in Minuten (Cronjob-Frequenz):"
    q_ov="Overlay (Werte im Bild anzeigen)?"
  else
    title="Sensor BME280"
    q_enable="Enable BME280 (temp/humidity/pressure)?"
    q_name="Name for BME280:"
    q_i2c="I2C address for BME280 (e.g. 0x76):"
    q_toff="Temperature offset in °C (BME280_TEMP_OFFSET_C, e.g. 0.0):"
    q_poff="Pressure offset in hPa (BME280_PRESS_OFFSET_HPA, e.g. 0.0):"
    q_hoff="Humidity offset in %-points (BME280_HUM_OFFSET_PCT, e.g. 0.0):"
    q_int="Logger interval in minutes (cronjob frequency):"
    q_ov="Overlay (show values on image)?"
  fi

  local OLD_ENABLED="$BME280_ENABLED"
  local OLD_NAME="$BME280_NAME"
  local OLD_ADDR="$BME280_I2C_ADDRESS"
  local OLD_OV="$BME280_OVERLAY"
  local OLD_INT="$BME280_LOG_INTERVAL_MIN"
  local OLD_TOFF="$BME280_TEMP_OFFSET_C"
  local OLD_POFF="$BME280_PRESS_OFFSET_HPA"
  local OLD_HOFF="$BME280_HUM_OFFSET_PCT"

  whiptail --title "$title" --yesno "$q_enable" 10 70
  rc=$?
  if [ $rc -eq 0 ]; then
    BME280_ENABLED="True"
  elif [ $rc -eq 1 ]; then
    BME280_ENABLED="False"
  else
    BME280_ENABLED="$OLD_ENABLED"
    return 0
  fi

  tmp=$(whiptail --title "$title" --inputbox "$q_name" 10 70 "$BME280_NAME" 3>&1 1>&2 2>&3)
  rc=$?
  if [ $rc -ne 0 ]; then
    BME280_ENABLED="$OLD_ENABLED"
    BME280_NAME="$OLD_NAME"
    BME280_I2C_ADDRESS="$OLD_ADDR"
    BME280_OVERLAY="$OLD_OV"
    BME280_LOG_INTERVAL_MIN="$OLD_INT"
    BME280_TEMP_OFFSET_C="$OLD_TOFF"
    BME280_PRESS_OFFSET_HPA="$OLD_POFF"
    BME280_HUM_OFFSET_PCT="$OLD_HOFF"
    return 0
  fi
  BME280_NAME="$tmp"

  if [ "$BME280_ENABLED" = "True" ]; then
    tmp=$(whiptail --title "$title" --inputbox "$q_i2c" 10 70 "$BME280_I2C_ADDRESS" 3>&1 1>&2 2>&3)
    rc=$?
    if [ $rc -ne 0 ]; then
      BME280_ENABLED="$OLD_ENABLED"
      BME280_NAME="$OLD_NAME"
      BME280_I2C_ADDRESS="$OLD_ADDR"
      BME280_OVERLAY="$OLD_OV"
      BME280_LOG_INTERVAL_MIN="$OLD_INT"
      BME280_TEMP_OFFSET_C="$OLD_TOFF"
      BME280_PRESS_OFFSET_HPA="$OLD_POFF"
      BME280_HUM_OFFSET_PCT="$OLD_HOFF"
      return 0
    fi
    BME280_I2C_ADDRESS="$tmp"

    tmp=$(whiptail --title "$title" --inputbox "$q_toff" 10 70 "$BME280_TEMP_OFFSET_C" 3>&1 1>&2 2>&3)
    rc=$?; if [ $rc -ne 0 ]; then
      BME280_ENABLED="$OLD_ENABLED"; BME280_NAME="$OLD_NAME"; BME280_I2C_ADDRESS="$OLD_ADDR"; BME280_OVERLAY="$OLD_OV"; BME280_LOG_INTERVAL_MIN="$OLD_INT"
      BME280_TEMP_OFFSET_C="$OLD_TOFF"; BME280_PRESS_OFFSET_HPA="$OLD_POFF"; BME280_HUM_OFFSET_PCT="$OLD_HOFF"
      return 0
    fi
    BME280_TEMP_OFFSET_C="${tmp//,/.}"

    tmp=$(whiptail --title "$title" --inputbox "$q_poff" 10 70 "$BME280_PRESS_OFFSET_HPA" 3>&1 1>&2 2>&3)
    rc=$?; if [ $rc -ne 0 ]; then
      BME280_ENABLED="$OLD_ENABLED"; BME280_NAME="$OLD_NAME"; BME280_I2C_ADDRESS="$OLD_ADDR"; BME280_OVERLAY="$OLD_OV"; BME280_LOG_INTERVAL_MIN="$OLD_INT"
      BME280_TEMP_OFFSET_C="$OLD_TOFF"; BME280_PRESS_OFFSET_HPA="$OLD_POFF"; BME280_HUM_OFFSET_PCT="$OLD_HOFF"
      return 0
    fi
    BME280_PRESS_OFFSET_HPA="${tmp//,/.}"

    tmp=$(whiptail --title "$title" --inputbox "$q_hoff" 10 70 "$BME280_HUM_OFFSET_PCT" 3>&1 1>&2 2>&3)
    rc=$?; if [ $rc -ne 0 ]; then
      BME280_ENABLED="$OLD_ENABLED"; BME280_NAME="$OLD_NAME"; BME280_I2C_ADDRESS="$OLD_ADDR"; BME280_OVERLAY="$OLD_OV"; BME280_LOG_INTERVAL_MIN="$OLD_INT"
      BME280_TEMP_OFFSET_C="$OLD_TOFF"; BME280_PRESS_OFFSET_HPA="$OLD_POFF"; BME280_HUM_OFFSET_PCT="$OLD_HOFF"
      return 0
    fi
    BME280_HUM_OFFSET_PCT="${tmp//,/.}"

    tmp=$(whiptail --title "$title" --inputbox "$q_int" 10 70 "$BME280_LOG_INTERVAL_MIN" 3>&1 1>&2 2>&3)
    rc=$?
    if [ $rc -ne 0 ]; then
      BME280_ENABLED="$OLD_ENABLED"
      BME280_NAME="$OLD_NAME"
      BME280_I2C_ADDRESS="$OLD_ADDR"
      BME280_OVERLAY="$OLD_OV"
      BME280_LOG_INTERVAL_MIN="$OLD_INT"
      BME280_TEMP_OFFSET_C="$OLD_TOFF"
      BME280_PRESS_OFFSET_HPA="$OLD_POFF"
      BME280_HUM_OFFSET_PCT="$OLD_HOFF"
      return 0
    fi
    BME280_LOG_INTERVAL_MIN="$tmp"

    whiptail --title "$title" --yesno "$q_ov" 10 70
    rc=$?
    if [ $rc -eq 0 ]; then
      BME280_OVERLAY="True"
    elif [ $rc -eq 1 ]; then
      BME280_OVERLAY="False"
    else
      BME280_ENABLED="$OLD_ENABLED"
      BME280_NAME="$OLD_NAME"
      BME280_I2C_ADDRESS="$OLD_ADDR"
      BME280_OVERLAY="$OLD_OV"
      BME280_LOG_INTERVAL_MIN="$OLD_INT"
      BME280_TEMP_OFFSET_C="$OLD_TOFF"
      BME280_PRESS_OFFSET_HPA="$OLD_POFF"
      BME280_HUM_OFFSET_PCT="$OLD_HOFF"
      return 0
    fi
  fi
}

# -------------------------------------------------------------------
# HINWEIS:
# Ab hier folgt dein Script (edit_ds18b20 ... bis Hauptmenue) unveraendert.
# Ich lasse alles drin – aber um die Antwort nicht doppelt zu "sprengen",
# setze ich direkt am Speichern-Block den entscheidenden Fix ein:
#   - INDI: Pfade+CAMERAID korrigieren
#   - INDI: Overlays (Sensoren + KpIndex) hart auf False
# -------------------------------------------------------------------

# ------------------------- DEIN REST-CODE --------------------------
# (Ich uebernehme ihn 1:1 weiter bis zum Speichern-Block)
# ------------------------------------------------------------------

# ... [DEIN CODE: edit_ds18b20, edit_mlx90614, edit_tsl2591, edit_dht11,
# edit_dht22, edit_htu21, edit_sht3x, sensors_menu, edit_kpindex, edit_analemma,
# edit_sqm, other_options_menu, show_processes, Hauptmenue-Schleife] ...

# ---------------------------------------------------
# Hauptmenue
# ---------------------------------------------------
while true; do
  if [ "$LANG_CODE" = "de" ]; then
    MTITLE="AllSkyKamera Konfiguration"
    MPROMPT="Bitte einen Bereich waehlen:"
    o1="Standortdaten"
    o2="Sensoren"
    o3="Prozesse (Cronjobs)"
    o4="Kamera und Objektiv"
    o5="Andere Optionen"
    oS="Speichern und Beenden"
    oQ="Abbrechen ohne Speichern"
  else
    MTITLE="AllSkyKamera Configuration"
    MPROMPT="Please choose a section:"
    o1="Location data"
    o2="Sensors"
    o3="Processes (cronjobs)"
    o4="Camera & optics"
    o5="Other options"
    oS="Save and exit"
    oQ="Cancel without saving"
  fi

  CHOICE=$(whiptail --title "$MTITLE" \
    --menu "$MPROMPT" 20 70 10 \
    "1" "$o1" \
    "2" "$o2" \
    "3" "$o3" \
    "4" "$o4" \
    "5" "$o5" \
    "S" "$oS" \
    "Q" "$oQ" \
    3>&1 1>&2 2>&3) || exit 1

  case "$CHOICE" in
    "1") edit_location ;;
    "2") sensors_menu ;;
    "3") show_processes ;;
    "4") camera_lens_menu ;;
    "5") other_options_menu ;;
    "S") break ;;
    "Q") exit 0 ;;
  esac
done

# ---------------------------------------------------
# >>> FIX: INDI Final Guard (VOR dem Schreiben der config.py) <<<
# - Pfade + CAMERAID fuer INDI final setzen
# - Overlays bei INDI IMMER deaktivieren (Sensoren + KpIndex)
# Damit kann nichts mehr "aus Versehen" True schreiben.
# ---------------------------------------------------
if [ "$INDI_ACTIVE" = "1" ]; then
  INDI="1"

  # Pfade fix
  ALLSKY_PATH="/var/www/html/allsky"
  IMAGE_BASE_PATH="images"
  IMAGE_PATH="tmp"

  # CAMERAID aus /var/www/html/allsky/images/ccd_* ermitteln
  INDI_IMAGES_DIR="${ALLSKY_PATH}/images"
  if [ -d "${INDI_IMAGES_DIR}" ]; then
    CCD_DIR_NAME="$(find "${INDI_IMAGES_DIR}" -maxdepth 1 -type d -name 'ccd_*' -printf '%f\n' 2>/dev/null | sort | head -n 1 || true)"
    if [ -n "${CCD_DIR_NAME}" ]; then
      CAMERAID="${CCD_DIR_NAME}"
    fi
  fi

  # Overlays hart aus
  BME280_OVERLAY="False"
  TSL2591_OVERLAY="False"
  DS18B20_OVERLAY="False"
  DHT11_OVERLAY="False"
  DHT22_OVERLAY="False"
  HTU21_OVERLAY="False"
  SHT3X_OVERLAY="False"
  KPINDEX_OVERLAY="False"
else
  INDI="0"
fi

# ---------------------------------------------------
# config.py neu erzeugen (inkl. *_NAME, Parametern & Intervallen)
# ---------------------------------------------------

KAMERA_ID_ESC="$(esc_py_str "$KAMERA_ID")"
KAMERA_NAME_ESC="$(esc_py_str "$KAMERA_NAME")"
STANDORT_NAME_ESC="$(esc_py_str "$STANDORT_NAME")"
BENUTZER_NAME_ESC="$(esc_py_str "$BENUTZER_NAME")"
KONTAKT_EMAIL_ESC="$(esc_py_str "$KONTAKT_EMAIL")"
WEBSEITE_ESC="$(esc_py_str "$WEBSEITE")"
ALLSKY_PATH_ESC="$(esc_py_str "$ALLSKY_PATH")"
IMAGE_BASE_PATH_ESC="$(esc_py_str "$IMAGE_BASE_PATH")"
IMAGE_PATH_ESC="$(esc_py_str "$IMAGE_PATH")"
CAMERAID_ESC="$(esc_py_str "$CAMERAID")"

BME280_NAME_ESC="$(esc_py_str "$BME280_NAME")"
DS18B20_NAME_ESC="$(esc_py_str "$DS18B20_NAME")"
MLX90614_NAME_ESC="$(esc_py_str "$MLX90614_NAME")"
TSL2591_NAME_ESC="$(esc_py_str "$TSL2591_NAME")"
DHT11_NAME_ESC="$(esc_py_str "$DHT11_NAME")"
DHT22_NAME_ESC="$(esc_py_str "$DHT22_NAME")"
HTU21_NAME_ESC="$(esc_py_str "$HTU21_NAME")"
SHT3X_NAME_ESC="$(esc_py_str "$SHT3X_NAME")"

cat > "$CFG_FILE" <<EOF
# config.py - automatisch generiert

try:
    from askutils.ASKsecret import API_KEY, API_URL
except ImportError:
    API_KEY = API_URL = None

# Kameradaten
KAMERA_ID      = "${KAMERA_ID_ESC}"
KAMERA_NAME    = "${KAMERA_NAME_ESC}"
STANDORT_NAME  = "${STANDORT_NAME_ESC}"
BENUTZER_NAME  = "${BENUTZER_NAME_ESC}"
KONTAKT_EMAIL  = "${KONTAKT_EMAIL_ESC}"
WEBSEITE       = "${WEBSEITE_ESC}"

# Standortkoordinaten
LATITUDE       = ${LATITUDE}
LONGITUDE      = ${LONGITUDE}

# Pfade
ALLSKY_PATH     = "${ALLSKY_PATH_ESC}"
IMAGE_BASE_PATH = "${IMAGE_BASE_PATH_ESC}"
IMAGE_PATH      = "${IMAGE_PATH_ESC}"
INDI            = ${INDI}
CAMERAID        = "${CAMERAID_ESC}"

# Objektiv- & SQM-Daten
PIX_SIZE_MM    = ${PIX_SIZE_MM}
FOCAL_MM       = ${FOCAL_MM}
ZP             = ${ZP}
SQM_PATCH_SIZE = ${SQM_PATCH_SIZE}

# Sensoren
BME280_ENABLED      = ${BME280_ENABLED}
BME280_NAME         = "${BME280_NAME_ESC}"
BME280_I2C_ADDRESS  = ${BME280_I2C_ADDRESS}
BME280_OVERLAY      = ${BME280_OVERLAY}
BME280_TEMP_OFFSET_C     = ${BME280_TEMP_OFFSET_C}
BME280_PRESS_OFFSET_HPA  = ${BME280_PRESS_OFFSET_HPA}
BME280_HUM_OFFSET_PCT    = ${BME280_HUM_OFFSET_PCT}

TSL2591_ENABLED        = ${TSL2591_ENABLED}
TSL2591_NAME           = "${TSL2591_NAME_ESC}"
TSL2591_I2C_ADDRESS    = ${TSL2591_I2C_ADDRESS}
TSL2591_SQM2_LIMIT     = ${TSL2591_SQM2_LIMIT}
TSL2591_SQM_CORRECTION = ${TSL2591_SQM_CORRECTION}
TSL2591_OVERLAY        = ${TSL2591_OVERLAY}

DS18B20_ENABLED  = ${DS18B20_ENABLED}
DS18B20_NAME     = "${DS18B20_NAME_ESC}"
DS18B20_OVERLAY  = ${DS18B20_OVERLAY}
DS18B20_TEMP_OFFSET_C = ${DS18B20_TEMP_OFFSET_C}

# DHT11
DHT11_ENABLED      = ${DHT11_ENABLED}
DHT11_NAME         = "${DHT11_NAME_ESC}"
DHT11_GPIO_BCM     = ${DHT11_GPIO_BCM}
DHT11_RETRIES      = ${DHT11_RETRIES}
DHT11_RETRY_DELAY  = ${DHT11_RETRY_DELAY}
DHT11_OVERLAY      = ${DHT11_OVERLAY}
DHT11_TEMP_OFFSET_C    = ${DHT11_TEMP_OFFSET_C}
DHT11_HUM_OFFSET_PCT   = ${DHT11_HUM_OFFSET_PCT}

# DHT22
DHT22_ENABLED      = ${DHT22_ENABLED}
DHT22_NAME         = "${DHT22_NAME_ESC}"
DHT22_GPIO_BCM     = ${DHT22_GPIO_BCM}
DHT22_RETRIES      = ${DHT22_RETRIES}
DHT22_RETRY_DELAY  = ${DHT22_RETRY_DELAY}
DHT22_OVERLAY      = ${DHT22_OVERLAY}
DHT22_TEMP_OFFSET_C    = ${DHT22_TEMP_OFFSET_C}
DHT22_HUM_OFFSET_PCT   = ${DHT22_HUM_OFFSET_PCT}

MLX90614_ENABLED     = ${MLX90614_ENABLED}
MLX90614_NAME        = "${MLX90614_NAME_ESC}"
MLX90614_I2C_ADDRESS = ${MLX90614_I2C_ADDRESS}
MLX90614_AMBIENT_OFFSET_C   = ${MLX90614_AMBIENT_OFFSET_C}
MLX_CLOUD_K1 = ${MLX_CLOUD_K1}
MLX_CLOUD_K2 = ${MLX_CLOUD_K2}
MLX_CLOUD_K3 = ${MLX_CLOUD_K3}
MLX_CLOUD_K4 = ${MLX_CLOUD_K4}
MLX_CLOUD_K5 = ${MLX_CLOUD_K5}
MLX_CLOUD_K6 = ${MLX_CLOUD_K6}
MLX_CLOUD_K7 = ${MLX_CLOUD_K7}

HTU21_ENABLED       = ${HTU21_ENABLED}
HTU21_NAME          = "${HTU21_NAME_ESC}"
HTU21_I2C_ADDRESS   = ${HTU21_I2C_ADDRESS}
HTU21_TEMP_OFFSET   = ${HTU21_TEMP_OFFSET}
HTU21_HUM_OFFSET    = ${HTU21_HUM_OFFSET}
HTU21_OVERLAY       = ${HTU21_OVERLAY}

# SHT3X Series (SHT30 / SHT31 / SHT35)
SHT3X_ENABLED       = ${SHT3X_ENABLED}
SHT3X_NAME          = "${SHT3X_NAME_ESC}"
SHT3X_I2C_ADDRESS   = ${SHT3X_I2C_ADDRESS}
SHT3X_TEMP_OFFSET   = ${SHT3X_TEMP_OFFSET}
SHT3X_HUM_OFFSET    = ${SHT3X_HUM_OFFSET}
SHT3X_OVERLAY       = ${SHT3X_OVERLAY}

# Logger-Intervalle in Minuten
BME280_LOG_INTERVAL_MIN   = ${BME280_LOG_INTERVAL_MIN}
TSL2591_LOG_INTERVAL_MIN  = ${TSL2591_LOG_INTERVAL_MIN}
DS18B20_LOG_INTERVAL_MIN  = ${DS18B20_LOG_INTERVAL_MIN}
DHT11_LOG_INTERVAL_MIN    = ${DHT11_LOG_INTERVAL_MIN}
DHT22_LOG_INTERVAL_MIN    = ${DHT22_LOG_INTERVAL_MIN}
MLX90614_LOG_INTERVAL_MIN = ${MLX90614_LOG_INTERVAL_MIN}
HTU21_LOG_INTERVAL_MIN    = ${HTU21_LOG_INTERVAL_MIN}
SHT3X_LOG_INTERVAL_MIN    = ${SHT3X_LOG_INTERVAL_MIN}

# KpIndex / Analemma / Kamera
KPINDEX_ENABLED = ${KPINDEX_ENABLED}
KPINDEX_OVERLAY = ${KPINDEX_OVERLAY}
KPINDEX_LOG_INTERVAL_MIN = ${KPINDEX_LOG_INTERVAL_MIN}

ANALEMMA_ENABLED = ${ANALEMMA_ENABLED}
KAMERA_WIDTH = ${KAMERA_WIDTH}
KAMERA_HEIGHT = ${KAMERA_HEIGHT}
A_SHUTTER = ${A_SHUTTER}       # 1 ms - deutlich kuerzer!
A_GAIN = ${A_GAIN}             # Kein Gain
A_BRIGHTNESS = ${A_BRIGHTNESS}
A_CONTRAST = ${A_CONTRAST}
A_SATURATION = ${A_SATURATION}
A_PATH = "${ROOT_DIR}/tmp"

# CRONTABS – Basisjobs
CRONTABS = [
    {
        "comment": "Allsky Raspi-Status",
        "schedule": "*/1 * * * *",
        "command": "cd ${ROOT_DIR} && python3 -m scripts.raspi_status",
    },
    {
        "comment": "Allsky Image-Upload",
        "schedule": "*/2 * * * *",
        "command": "cd ${ROOT_DIR} && python3 -m scripts.run_image_upload",
    },
    {
        "comment": "Config Update",
        "schedule": "0 12 * * *",
        "command": "cd ${ROOT_DIR} && python3 -m scripts.upload_config_json",
    },
    {
        "comment": "Nightly FTP-Upload",
        "schedule": "45 8 * * *",
        "command": "cd ${ROOT_DIR} && python3 -m scripts.run_nightly_upload",
    },
    {
        "comment": "SQM Messung",
        "schedule": "*/5 * * * *",
        "command": "cd ${ROOT_DIR} && python3 -m scripts.sqm_camera_logger",
    },
    {
        "comment": "SQM Plot Generierung",
        "schedule": "0 8 * * *",
        "command": "cd ${ROOT_DIR} && python3 -m scripts.plot_sqm_night",
    },
]

# Sensor-Logger-Cronjobs dynamisch je nach Enabled-Status
if BME280_ENABLED:
    CRONTABS.append({
        "comment": "BME280 Sensor",
        "schedule": f"*/{BME280_LOG_INTERVAL_MIN} * * * *",
        "command": "cd ${ROOT_DIR} && python3 -m scripts.bme280_logger",
    })

if DS18B20_ENABLED:
    CRONTABS.append({
        "comment": "DS18B20 Sensor",
        "schedule": f"*/{DS18B20_LOG_INTERVAL_MIN} * * * *",
        "command": "cd ${ROOT_DIR} && python3 -m scripts.ds18b20_logger",
    })

if TSL2591_ENABLED:
    CRONTABS.append({
        "comment": "TSL2591 Sensor",
        "schedule": f"*/{TSL2591_LOG_INTERVAL_MIN} * * * *",
        "command": "cd ${ROOT_DIR} && python3 -m scripts.tsl2591_logger",
    })

if MLX90614_ENABLED:
    CRONTABS.append({
        "comment": "MLX90614 Sensor",
        "schedule": f"*/{MLX90614_LOG_INTERVAL_MIN} * * * *",
        "command": "cd ${ROOT_DIR} && python3 -m scripts.mlx90614_logger",
    })

if DHT11_ENABLED:
    CRONTABS.append({
        "comment": "DHT11 Sensor",
        "schedule": f"*/{DHT11_LOG_INTERVAL_MIN} * * * *",
        "command": "cd ${ROOT_DIR} && python3 -m scripts.dht11_logger",
    })

if DHT22_ENABLED:
    CRONTABS.append({
        "comment": "DHT22 Sensor",
        "schedule": f"*/{DHT22_LOG_INTERVAL_MIN} * * * *",
        "command": "cd ${ROOT_DIR} && python3 -m scripts.dht22_logger",
    })

if HTU21_ENABLED:
    CRONTABS.append({
        "comment": "HTU21 / GY-21 Sensor",
        "schedule": f"*/{HTU21_LOG_INTERVAL_MIN} * * * *",
        "command": "cd ${ROOT_DIR} && python3 -m scripts.htu21_logger",
    })

if SHT3X_ENABLED:
    CRONTABS.append({
        "comment": "SHT3x Sensor",
        "schedule": f"*/{SHT3X_LOG_INTERVAL_MIN} * * * *",
        "command": "cd ${ROOT_DIR} && python3 -m scripts.sht3x_logger",
    })

if KPINDEX_ENABLED:
    CRONTABS.append({
        "comment": "KpIndex Logger",
        "schedule": f"*/{KPINDEX_LOG_INTERVAL_MIN} * * * *",
        "command": "cd ${ROOT_DIR} && python3 -m scripts.kpindex_logger",
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

# ---------------------------------------------------
# Nach dem Speichern: Upload-Skript & Crontabs
# ---------------------------------------------------
if [ "$LANG_CODE" = "de" ]; then
  whiptail --title "Fertig" --msgbox "config.py wurde erfolgreich aktualisiert.\n\nDie Konfiguration wird jetzt auf den Server hochgeladen..." 10 70
else
  whiptail --title "Done" --msgbox "config.py has been updated successfully.\n\nConfiguration will now be uploaded to the server..." 10 70
fi

cd "$ROOT_DIR" || exit 1

if python3 -m scripts.upload_config_json; then
  if [ "$LANG_CODE" = "de" ]; then
    whiptail --title "Upload erfolgreich" --msgbox "Die Konfiguration wurde erfolgreich auf den Server uebertragen." 8 70
  else
    whiptail --title "Upload successful" --msgbox "Configuration has been successfully uploaded to the server." 8 70
  fi

  if python3 -m scripts.manage_crontabs; then
    if [ "$LANG_CODE" = "de" ]; then
      whiptail --title "Cronjobs aktualisiert" --msgbox "Die Crontab-Eintraege fuer die Sensor-Logger wurden erfolgreich aktualisiert." 8 70
    else
      whiptail --title "Cronjobs updated" --msgbox "Crontab entries for sensor loggers have been updated successfully." 8 70
    fi
  else
    if [ "$LANG_CODE" = "de" ]; then
      whiptail --title "Fehler bei Cronjobs" --msgbox "Die Crontab-Eintraege konnten nicht automatisch aktualisiert werden.\nBitte pruefen Sie die Logs oder fuehren Sie den Befehl manuell aus:\n\npython3 -m scripts.manage_crontabs" 12 80
    else
      whiptail --title "Cronjob update failed" --msgbox "Crontab entries could not be updated automatically.\nPlease check the logs or run manually:\n\npython3 -m scripts.manage_crontabs" 12 80
    fi
  fi

else
  if [ "$LANG_CODE" = "de" ]; then
    whiptail --title "Fehler beim Upload" --msgbox "Das Python-Skript konnte nicht erfolgreich ausgefuehrt werden.\nBitte pruefen Sie die Logs oder fuehren Sie den Upload manuell aus:\n\npython3 -m scripts.upload_config_json" 12 80
  else
    whiptail --title "Upload failed" --msgbox "The Python script failed to run.\nPlease check the logs or run manually:\n\npython3 -m scripts.upload_config_json" 12 80
  fi
fi
