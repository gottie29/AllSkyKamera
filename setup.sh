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
# Sprache wählen (de / en) – Deutsch ist Standard
# ---------------------------------------------------
LANG_CODE="de"
LANG_CHOICE=$(whiptail --title "Sprache / Language" \
  --menu "Bitte Sprache wählen / Please choose language:" 15 60 2 \
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

# Strings für Python escapen (für Strings in config.py)
esc_py_str() {
    local s="$1"
    s="${s//\\/\\\\}"   # Backslashes
    s="${s//\"/\\\"}"   # Doppelte Anführungszeichen
    echo "$s"
}

# Zahl wie "118" wieder in "0x76" umwandeln (für I2C-Adressen)
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

# bool -> Status-Text für Menü
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

# Sensor-Parameter
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

# Logger-Intervalle (Minuten)
BME280_LOG_INTERVAL_MIN="$(get_val "BME280_LOG_INTERVAL_MIN")"
TSL2591_LOG_INTERVAL_MIN="$(get_val "TSL2591_LOG_INTERVAL_MIN")"
DS18B20_LOG_INTERVAL_MIN="$(get_val "DS18B20_LOG_INTERVAL_MIN")"
DHT11_LOG_INTERVAL_MIN="$(get_val "DHT11_LOG_INTERVAL_MIN")"
DHT22_LOG_INTERVAL_MIN="$(get_val "DHT22_LOG_INTERVAL_MIN")"
MLX90614_LOG_INTERVAL_MIN="$(get_val "MLX90614_LOG_INTERVAL_MIN")"

# Neue Sensor-Namen
BME280_NAME="$(get_val "BME280_NAME")"
DS18B20_NAME="$(get_val "DS18B20_NAME")"
MLX90614_NAME="$(get_val "MLX90614_NAME")"
TSL2591_NAME="$(get_val "TSL2591_NAME")"
DHT11_NAME="$(get_val "DHT11_NAME")"
DHT22_NAME="$(get_val "DHT22_NAME")"

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

[ -z "$ALLSKY_PATH" ] && ALLSKY_PATH="/var/www/html/allsky"
[ -z "$IMAGE_BASE_PATH" ] && IMAGE_BASE_PATH="images"
[ -z "$IMAGE_PATH" ] && IMAGE_PATH="tmp"
[ -z "$INDI" ] && INDI="0"
[ -z "$CAMERAID" ] && CAMERAID="ccd_002f6961-ba9f-4387-8c2e-09ec5c72f55d"

[ -z "$BME280_ENABLED" ] && BME280_ENABLED="True"
[ -z "$TSL2591_ENABLED" ] && TSL2591_ENABLED="True"
[ -z "$DS18B20_ENABLED" ] && DS18B20_ENABLED="True"
[ -z "$DHT11_ENABLED" ] && DHT11_ENABLED="False"
[ -z "$DHT22_ENABLED" ] && DHT22_ENABLED="True"
[ -z "$MLX90614_ENABLED" ] && MLX90614_ENABLED="True"

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

[ -z "$BME280_NAME" ] && BME280_NAME="BME280"
[ -z "$DS18B20_NAME" ] && DS18B20_NAME="DS18B20"
[ -z "$MLX90614_NAME" ] && MLX90614_NAME="MLX90614"
[ -z "$TSL2591_NAME" ] && TSL2591_NAME="TSL2591"
[ -z "$DHT11_NAME" ] && DHT11_NAME="DHT11"
[ -z "$DHT22_NAME" ] && DHT22_NAME="DHT22"

# Standard-Logger-Intervalle in Minuten
[ -z "$BME280_LOG_INTERVAL_MIN" ]   && BME280_LOG_INTERVAL_MIN="1"
[ -z "$TSL2591_LOG_INTERVAL_MIN" ]  && TSL2591_LOG_INTERVAL_MIN="1"
[ -z "$DS18B20_LOG_INTERVAL_MIN" ]  && DS18B20_LOG_INTERVAL_MIN="1"
[ -z "$DHT11_LOG_INTERVAL_MIN" ]    && DHT11_LOG_INTERVAL_MIN="1"
[ -z "$DHT22_LOG_INTERVAL_MIN" ]    && DHT22_LOG_INTERVAL_MIN="1"
[ -z "$MLX90614_LOG_INTERVAL_MIN" ] && MLX90614_LOG_INTERVAL_MIN="1"

# Defaults für Kamera / Objektiv / SQM / Analemma / KpIndex
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


# I2C-Adressen in schöne Hex-Notation bringen
BME280_I2C_ADDRESS="$(normalize_hex_literal "$BME280_I2C_ADDRESS")"
TSL2591_I2C_ADDRESS="$(normalize_hex_literal "$TSL2591_I2C_ADDRESS")"
MLX90614_I2C_ADDRESS="$(normalize_hex_literal "$MLX90614_I2C_ADDRESS")"

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
    lbl_lon="Längengrad (LONGITUDE, z.B. 13.1234)"
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

  # Alte Werte sichern (für Rollback)
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

  # Längengrad
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
    q_h="Sensorhöhe in Pixel (KAMERA_HEIGHT):"
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
    q_pix="Pixelgröße in mm (PIX_SIZE_MM, z.B. 0.00155):"
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
    mp="Bitte einen Bereich wählen:"
    back_label="Zurück"
    o_cam="Kamera (Sensorgröße)"
    o_lens="Objektiv (Pixelgröße/Brennweite)"
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
# Sensor-Untermenüs
# ---------------------------------------------------

edit_bme280() {
  local title q_enable q_name q_i2c q_int q_ov rc tmp
  if [ "$LANG_CODE" = "de" ]; then
    title="Sensor BME280"
    q_enable="BME280 (Temp/Feuchte/Druck) aktivieren?"
    q_name="Name für BME280:"
    q_i2c="I2C-Adresse des BME280 (z.B. 0x76):"
    q_int="Logger-Intervall in Minuten (Cronjob-Frequenz):"
    q_ov="Overlay (Werte im Bild anzeigen)?"
  else
    title="Sensor BME280"
    q_enable="Enable BME280 (temp/humidity/pressure)?"
    q_name="Name for BME280:"
    q_i2c="I2C address for BME280 (e.g. 0x76):"
    q_int="Logger interval in minutes (cronjob frequency):"
    q_ov="Overlay (show values on image)?"
  fi

  local OLD_ENABLED="$BME280_ENABLED"
  local OLD_NAME="$BME280_NAME"
  local OLD_ADDR="$BME280_I2C_ADDRESS"
  local OLD_OV="$BME280_OVERLAY"
  local OLD_INT="$BME280_LOG_INTERVAL_MIN"

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
      return 0
    fi
    BME280_I2C_ADDRESS="$tmp"

    tmp=$(whiptail --title "$title" --inputbox "$q_int" 10 70 "$BME280_LOG_INTERVAL_MIN" 3>&1 1>&2 2>&3)
    rc=$?
    if [ $rc -ne 0 ]; then
      BME280_ENABLED="$OLD_ENABLED"
      BME280_NAME="$OLD_NAME"
      BME280_I2C_ADDRESS="$OLD_ADDR"
      BME280_OVERLAY="$OLD_OV"
      BME280_LOG_INTERVAL_MIN="$OLD_INT"
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
      return 0
    fi
  fi
}

edit_ds18b20() {
  local title q_enable q_name q_ov q_int rc tmp
  if [ "$LANG_CODE" = "de" ]; then
    title="Sensor DS18B20"
    q_enable="DS18B20 (Temperatur) aktivieren?"
    q_name="Name für DS18B20:"
    q_ov="Overlay (Werte im Bild anzeigen)?"
    q_int="Logger-Intervall in Minuten (Cronjob-Frequenz):"
  else
    title="Sensor DS18B20"
    q_enable="Enable DS18B20 (temperature)?"
    q_name="Name for DS18B20:"
    q_ov="Overlay (show values on image)?"
    q_int="Logger interval in minutes (cronjob frequency):"
  fi

  local OLD_ENABLED="$DS18B20_ENABLED"
  local OLD_NAME="$DS18B20_NAME"
  local OLD_OV="$DS18B20_OVERLAY"
  local OLD_INT="$DS18B20_LOG_INTERVAL_MIN"

  whiptail --title "$title" --yesno "$q_enable" 10 70
  rc=$?
  if [ $rc -eq 0 ]; then
    DS18B20_ENABLED="True"
  elif [ $rc -eq 1 ]; then
    DS18B20_ENABLED="False"
  else
    DS18B20_ENABLED="$OLD_ENABLED"
    return 0
  fi

  tmp=$(whiptail --title "$title" --inputbox "$q_name" 10 70 "$DS18B20_NAME" 3>&1 1>&2 2>&3)
  rc=$?
  if [ $rc -ne 0 ]; then
    DS18B20_ENABLED="$OLD_ENABLED"
    DS18B20_NAME="$OLD_NAME"
    DS18B20_OVERLAY="$OLD_OV"
    DS18B20_LOG_INTERVAL_MIN="$OLD_INT"
    return 0
  fi
  DS18B20_NAME="$tmp"

  if [ "$DS18B20_ENABLED" = "True" ]; then
    whiptail --title "$title" --yesno "$q_ov" 10 70
    rc=$?
    if [ $rc -eq 0 ]; then
      DS18B20_OVERLAY="True"
    elif [ $rc -eq 1 ]; then
      DS18B20_OVERLAY="False"
    else
      DS18B20_ENABLED="$OLD_ENABLED"
      DS18B20_NAME="$OLD_NAME"
      DS18B20_OVERLAY="$OLD_OV"
      DS18B20_LOG_INTERVAL_MIN="$OLD_INT"
      return 0
    fi

    tmp=$(whiptail --title "$title" --inputbox "$q_int" 10 70 "$DS18B20_LOG_INTERVAL_MIN" 3>&1 1>&2 2>&3)
    rc=$?
    if [ $rc -ne 0 ]; then
      DS18B20_ENABLED="$OLD_ENABLED"
      DS18B20_NAME="$OLD_NAME"
      DS18B20_OVERLAY="$OLD_OV"
      DS18B20_LOG_INTERVAL_MIN="$OLD_INT"
      return 0
    fi
    DS18B20_LOG_INTERVAL_MIN="$tmp"
  fi
}

edit_mlx90614() {
  local title q_enable q_name q_i2c q_int rc tmp
  if [ "$LANG_CODE" = "de" ]; then
    title="Sensor MLX90614"
    q_enable="MLX90614 (IR-Temperatur) aktivieren?"
    q_name="Name für MLX90614:"
    q_i2c="I2C-Adresse des MLX90614 (z.B. 0x5a):"
    q_int="Logger-Intervall in Minuten (Cronjob-Frequenz):"
  else
    title="Sensor MLX90614"
    q_enable="Enable MLX90614 (IR temperature)?"
    q_name="Name for MLX90614:"
    q_i2c="I2C address for MLX90614 (e.g. 0x5a):"
    q_int="Logger interval in minutes (cronjob frequency):"
  fi

  local OLD_ENABLED="$MLX90614_ENABLED"
  local OLD_NAME="$MLX90614_NAME"
  local OLD_ADDR="$MLX90614_I2C_ADDRESS"
  local OLD_INT="$MLX90614_LOG_INTERVAL_MIN"

  whiptail --title "$title" --yesno "$q_enable" 10 70
  rc=$?
  if [ $rc -eq 0 ]; then
    MLX90614_ENABLED="True"
  elif [ $rc -eq 1 ]; then
    MLX90614_ENABLED="False"
  else
    MLX90614_ENABLED="$OLD_ENABLED"
    return 0
  fi

  tmp=$(whiptail --title "$title" --inputbox "$q_name" 10 70 "$MLX90614_NAME" 3>&1 1>&2 2>&3)
  rc=$?
  if [ $rc -ne 0 ]; then
    MLX90614_ENABLED="$OLD_ENABLED"
    MLX90614_NAME="$OLD_NAME"
    MLX90614_I2C_ADDRESS="$OLD_ADDR"
    MLX90614_LOG_INTERVAL_MIN="$OLD_INT"
    return 0
  fi
  MLX90614_NAME="$tmp"

  if [ "$MLX90614_ENABLED" = "True" ]; then
    tmp=$(whiptail --title "$title" --inputbox "$q_i2c" 10 70 "$MLX90614_I2C_ADDRESS" 3>&1 1>&2 2>&3)
    rc=$?
    if [ $rc -ne 0 ]; then
      MLX90614_ENABLED="$OLD_ENABLED"
      MLX90614_NAME="$OLD_NAME"
      MLX90614_I2C_ADDRESS="$OLD_ADDR"
      MLX90614_LOG_INTERVAL_MIN="$OLD_INT"
      return 0
    fi
    MLX90614_I2C_ADDRESS="$tmp"

    tmp=$(whiptail --title "$title" --inputbox "$q_int" 10 70 "$MLX90614_LOG_INTERVAL_MIN" 3>&1 1>&2 2>&3)
    rc=$?
    if [ $rc -ne 0 ]; then
      MLX90614_ENABLED="$OLD_ENABLED"
      MLX90614_NAME="$OLD_NAME"
      MLX90614_I2C_ADDRESS="$OLD_ADDR"
      MLX90614_LOG_INTERVAL_MIN="$OLD_INT"
      return 0
    fi
    MLX90614_LOG_INTERVAL_MIN="$tmp"
  fi
}

edit_tsl2591() {
  local title q_enable q_name q_i2c q_lmt q_corr q_ov q_int rc tmp
  if [ "$LANG_CODE" = "de" ]; then
    title="Sensor TSL2591"
    q_enable="TSL2591 (SQM / Himmelshelligkeit) aktivieren?"
    q_name="Name für TSL2591:"
    q_i2c="I2C-Adresse des TSL2591 (z.B. 0x29):"
    q_lmt="SQM2 Grenzwert (TSL2591_SQM2_LIMIT, z.B. 0.0):"
    q_corr="SQM Korrektur (TSL2591_SQM_CORRECTION, z.B. 0.0):"
    q_ov="Overlay (Werte im Bild anzeigen)?"
    q_int="Logger-Intervall in Minuten (Cronjob-Frequenz):"
  else
    title="Sensor TSL2591"
    q_enable="Enable TSL2591 (SQM / sky brightness)?"
    q_name="Name for TSL2591:"
    q_i2c="I2C address for TSL2591 (e.g. 0x29):"
    q_lmt="SQM2 limit (TSL2591_SQM2_LIMIT, e.g. 0.0):"
    q_corr="SQM correction (TSL2591_SQM_CORRECTION, e.g. 0.0):"
    q_ov="Overlay (show values on image)?"
    q_int="Logger interval in minutes (cronjob frequency):"
  fi

  local OLD_ENABLED="$TSL2591_ENABLED"
  local OLD_NAME="$TSL2591_NAME"
  local OLD_ADDR="$TSL2591_I2C_ADDRESS"
  local OLD_LMT="$TSL2591_SQM2_LIMIT"
  local OLD_CORR="$TSL2591_SQM_CORRECTION"
  local OLD_OV="$TSL2591_OVERLAY"
  local OLD_INT="$TSL2591_LOG_INTERVAL_MIN"

  whiptail --title "$title" --yesno "$q_enable" 10 70
  rc=$?
  if [ $rc -eq 0 ]; then
    TSL2591_ENABLED="True"
  elif [ $rc -eq 1 ]; then
    TSL2591_ENABLED="False"
  else
    TSL2591_ENABLED="$OLD_ENABLED"
    return 0
  fi

  tmp=$(whiptail --title "$title" --inputbox "$q_name" 10 70 "$TSL2591_NAME" 3>&1 1>&2 2>&3)
  rc=$?
  if [ $rc -ne 0 ]; then
    TSL2591_ENABLED="$OLD_ENABLED"
    TSL2591_NAME="$OLD_NAME"
    TSL2591_I2C_ADDRESS="$OLD_ADDR"
    TSL2591_SQM2_LIMIT="$OLD_LMT"
    TSL2591_SQM_CORRECTION="$OLD_CORR"
    TSL2591_OVERLAY="$OLD_OV"
    TSL2591_LOG_INTERVAL_MIN="$OLD_INT"
    return 0
  fi
  TSL2591_NAME="$tmp"

  if [ "$TSL2591_ENABLED" = "True" ]; then
    tmp=$(whiptail --title "$title" --inputbox "$q_i2c" 10 70 "$TSL2591_I2C_ADDRESS" 3>&1 1>&2 2>&3)
    rc=$?
    if [ $rc -ne 0 ]; then
      TSL2591_ENABLED="$OLD_ENABLED"
      TSL2591_NAME="$OLD_NAME"
      TSL2591_I2C_ADDRESS="$OLD_ADDR"
      TSL2591_SQM2_LIMIT="$OLD_LMT"
      TSL2591_SQM_CORRECTION="$OLD_CORR"
      TSL2591_OVERLAY="$OLD_OV"
      TSL2591_LOG_INTERVAL_MIN="$OLD_INT"
      return 0
    fi
    TSL2591_I2C_ADDRESS="$tmp"

    tmp=$(whiptail --title "$title" --inputbox "$q_lmt" 10 70 "$TSL2591_SQM2_LIMIT" 3>&1 1>&2 2>&3)
    rc=$?
    if [ $rc -ne 0 ]; then
      TSL2591_ENABLED="$OLD_ENABLED"
      TSL2591_NAME="$OLD_NAME"
      TSL2591_I2C_ADDRESS="$OLD_ADDR"
      TSL2591_SQM2_LIMIT="$OLD_LMT"
      TSL2591_SQM_CORRECTION="$OLD_CORR"
      TSL2591_OVERLAY="$OLD_OV"
      TSL2591_LOG_INTERVAL_MIN="$OLD_INT"
      return 0
    fi
    TSL2591_SQM2_LIMIT="${tmp//,/.}"

    tmp=$(whiptail --title "$title" --inputbox "$q_corr" 10 70 "$TSL2591_SQM_CORRECTION" 3>&1 1>&2 2>&3)
    rc=$?
    if [ $rc -ne 0 ]; then
      TSL2591_ENABLED="$OLD_ENABLED"
      TSL2591_NAME="$OLD_NAME"
      TSL2591_I2C_ADDRESS="$OLD_ADDR"
      TSL2591_SQM2_LIMIT="$OLD_LMT"
      TSL2591_SQM_CORRECTION="$OLD_CORR"
      TSL2591_OVERLAY="$OLD_OV"
      TSL2591_LOG_INTERVAL_MIN="$OLD_INT"
      return 0
    fi
    TSL2591_SQM_CORRECTION="${tmp//,/.}"

    whiptail --title "$title" --yesno "$q_ov" 10 70
    rc=$?
    if [ $rc -eq 0 ]; then
      TSL2591_OVERLAY="True"
    elif [ $rc -eq 1 ]; then
      TSL2591_OVERLAY="False"
    else
      TSL2591_ENABLED="$OLD_ENABLED"
      TSL2591_NAME="$OLD_NAME"
      TSL2591_I2C_ADDRESS="$OLD_ADDR"
      TSL2591_SQM2_LIMIT="$OLD_LMT"
      TSL2591_SQM_CORRECTION="$OLD_CORR"
      TSL2591_OVERLAY="$OLD_OV"
      TSL2591_LOG_INTERVAL_MIN="$OLD_INT"
      return 0
    fi

    tmp=$(whiptail --title "$title" --inputbox "$q_int" 10 70 "$TSL2591_LOG_INTERVAL_MIN" 3>&1 1>&2 2>&3)
    rc=$?
    if [ $rc -ne 0 ]; then
      TSL2591_ENABLED="$OLD_ENABLED"
      TSL2591_NAME="$OLD_NAME"
      TSL2591_I2C_ADDRESS="$OLD_ADDR"
      TSL2591_SQM2_LIMIT="$OLD_LMT"
      TSL2591_SQM_CORRECTION="$OLD_CORR"
      TSL2591_OVERLAY="$OLD_OV"
      TSL2591_LOG_INTERVAL_MIN="$OLD_INT"
      return 0
    fi
    TSL2591_LOG_INTERVAL_MIN="$tmp"
  fi
}

edit_dht11() {
  local title q_enable q_name q_gpio q_ret q_delay q_ov q_int rc tmp
  if [ "$LANG_CODE" = "de" ]; then
    title="Sensor DHT11"
    q_enable="DHT11 aktivieren?"
    q_name="Name für DHT11:"
    q_gpio="GPIO (BCM-Nummer, z.B. 6):"
    q_ret="Anzahl Wiederholungen (DHT11_RETRIES):"
    q_delay="Retry-Delay in Sekunden (DHT11_RETRY_DELAY, z.B. 0.3):"
    q_ov="Overlay (Werte im Bild anzeigen)?"
    q_int="Logger-Intervall in Minuten (Cronjob-Frequenz):"
  else
    title="Sensor DHT11"
    q_enable="Enable DHT11?"
    q_name="Name for DHT11:"
    q_gpio="GPIO (BCM number, e.g. 6):"
    q_ret="Number of retries (DHT11_RETRIES):"
    q_delay="Retry delay in seconds (DHT11_RETRY_DELAY, e.g. 0.3):"
    q_ov="Overlay (show values on image)?"
    q_int="Logger interval in minutes (cronjob frequency):"
  fi

  local OLD_ENABLED="$DHT11_ENABLED"
  local OLD_NAME="$DHT11_NAME"
  local OLD_GPIO="$DHT11_GPIO_BCM"
  local OLD_RET="$DHT11_RETRIES"
  local OLD_DEL="$DHT11_RETRY_DELAY"
  local OLD_OV="$DHT11_OVERLAY"
  local OLD_INT="$DHT11_LOG_INTERVAL_MIN"

  whiptail --title "$title" --yesno "$q_enable" 10 70
  rc=$?
  if [ $rc -eq 0 ]; then
    DHT11_ENABLED="True"
  elif [ $rc -eq 1 ]; then
    DHT11_ENABLED="False"
  else
    DHT11_ENABLED="$OLD_ENABLED"
    return 0
  fi

  tmp=$(whiptail --title "$title" --inputbox "$q_name" 10 70 "$DHT11_NAME" 3>&1 1>&2 2>&3)
  rc=$?
  if [ $rc -ne 0 ]; then
    DHT11_ENABLED="$OLD_ENABLED"
    DHT11_NAME="$OLD_NAME"
    DHT11_GPIO_BCM="$OLD_GPIO"
    DHT11_RETRIES="$OLD_RET"
    DHT11_RETRY_DELAY="$OLD_DEL"
    DHT11_OVERLAY="$OLD_OV"
    DHT11_LOG_INTERVAL_MIN="$OLD_INT"
    return 0
  fi
  DHT11_NAME="$tmp"

  if [ "$DHT11_ENABLED" = "True" ]; then
    tmp=$(whiptail --title "$title" --inputbox "$q_gpio" 10 70 "$DHT11_GPIO_BCM" 3>&1 1>&2 2>&3)
    rc=$?
    if [ $rc -ne 0 ]; then
      DHT11_ENABLED="$OLD_ENABLED"
      DHT11_NAME="$OLD_NAME"
      DHT11_GPIO_BCM="$OLD_GPIO"
      DHT11_RETRIES="$OLD_RET"
      DHT11_RETRY_DELAY="$OLD_DEL"
      DHT11_OVERLAY="$OLD_OV"
      DHT11_LOG_INTERVAL_MIN="$OLD_INT"
      return 0
    fi
    DHT11_GPIO_BCM="$tmp"

    tmp=$(whiptail --title "$title" --inputbox "$q_ret" 10 70 "$DHT11_RETRIES" 3>&1 1>&2 2>&3)
    rc=$?
    if [ $rc -ne 0 ]; then
      DHT11_ENABLED="$OLD_ENABLED"
      DHT11_NAME="$OLD_NAME"
      DHT11_GPIO_BCM="$OLD_GPIO"
      DHT11_RETRIES="$OLD_RET"
      DHT11_RETRY_DELAY="$OLD_DEL"
      DHT11_OVERLAY="$OLD_OV"
      DHT11_LOG_INTERVAL_MIN="$OLD_INT"
      return 0
    fi
    DHT11_RETRIES="$tmp"

    tmp=$(whiptail --title "$title" --inputbox "$q_delay" 10 70 "$DHT11_RETRY_DELAY" 3>&1 1>&2 2>&3)
    rc=$?
    if [ $rc -ne 0 ]; then
      DHT11_ENABLED="$OLD_ENABLED"
      DHT11_NAME="$OLD_NAME"
      DHT11_GPIO_BCM="$OLD_GPIO"
      DHT11_RETRIES="$OLD_RET"
      DHT11_RETRY_DELAY="$OLD_DEL"
      DHT11_OVERLAY="$OLD_OV"
      DHT11_LOG_INTERVAL_MIN="$OLD_INT"
      return 0
    fi
    DHT11_RETRY_DELAY="${tmp//,/.}"

    whiptail --title "$title" --yesno "$q_ov" 10 70
    rc=$?
    if [ $rc -eq 0 ]; then
      DHT11_OVERLAY="True"
    elif [ $rc -eq 1 ]; then
      DHT11_OVERLAY="False"
    else
      DHT11_ENABLED="$OLD_ENABLED"
      DHT11_NAME="$OLD_NAME"
      DHT11_GPIO_BCM="$OLD_GPIO"
      DHT11_RETRIES="$OLD_RET"
      DHT11_RETRY_DELAY="$OLD_DEL"
      DHT11_OVERLAY="$OLD_OV"
      DHT11_LOG_INTERVAL_MIN="$OLD_INT"
      return 0
    fi

    tmp=$(whiptail --title "$title" --inputbox "$q_int" 10 70 "$DHT11_LOG_INTERVAL_MIN" 3>&1 1>&2 2>&3)
    rc=$?
    if [ $rc -ne 0 ]; then
      DHT11_ENABLED="$OLD_ENABLED"
      DHT11_NAME="$OLD_NAME"
      DHT11_GPIO_BCM="$OLD_GPIO"
      DHT11_RETRIES="$OLD_RET"
      DHT11_RETRY_DELAY="$OLD_DEL"
      DHT11_OVERLAY="$OLD_OV"
      DHT11_LOG_INTERVAL_MIN="$OLD_INT"
      return 0
    fi
    DHT11_LOG_INTERVAL_MIN="$tmp"
  fi
}

edit_dht22() {
  local title q_enable q_name q_gpio q_ret q_delay q_ov q_int rc tmp
  if [ "$LANG_CODE" = "de" ]; then
    title="Sensor DHT22"
    q_enable="DHT22 aktivieren?"
    q_name="Name für DHT22:"
    q_gpio="GPIO (BCM-Nummer, z.B. 6):"
    q_ret="Anzahl Wiederholungen (DHT22_RETRIES):"
    q_delay="Retry-Delay in Sekunden (DHT22_RETRY_DELAY, z.B. 12):"
    q_ov="Overlay (Werte im Bild anzeigen)?"
    q_int="Logger-Intervall in Minuten (Cronjob-Frequenz):"
  else
    title="Sensor DHT22"
    q_enable="Enable DHT22?"
    q_name="Name for DHT22:"
    q_gpio="GPIO (BCM number, e.g. 6):"
    q_ret="Number of retries (DHT22_RETRIES):"
    q_delay="Retry delay in seconds (DHT22_RETRY_DELAY, e.g. 12):"
    q_ov="Overlay (show values on image)?"
    q_int="Logger interval in minutes (cronjob frequency):"
  fi

  local OLD_ENABLED="$DHT22_ENABLED"
  local OLD_NAME="$DHT22_NAME"
  local OLD_GPIO="$DHT22_GPIO_BCM"
  local OLD_RET="$DHT22_RETRIES"
  local OLD_DEL="$DHT22_RETRY_DELAY"
  local OLD_OV="$DHT22_OVERLAY"
  local OLD_INT="$DHT22_LOG_INTERVAL_MIN"

  whiptail --title "$title" --yesno "$q_enable" 10 70
  rc=$?
  if [ $rc -eq 0 ]; then
    DHT22_ENABLED="True"
  elif [ $rc -eq 1 ]; then
    DHT22_ENABLED="False"
  else
    DHT22_ENABLED="$OLD_ENABLED"
    return 0
  fi

  tmp=$(whiptail --title "$title" --inputbox "$q_name" 10 70 "$DHT22_NAME" 3>&1 1>&2 2>&3)
  rc=$?
  if [ $rc -ne 0 ]; then
    DHT22_ENABLED="$OLD_ENABLED"
    DHT22_NAME="$OLD_NAME"
    DHT22_GPIO_BCM="$OLD_GPIO"
    DHT22_RETRIES="$OLD_RET"
    DHT22_RETRY_DELAY="$OLD_DEL"
    DHT22_OVERLAY="$OLD_OV"
    DHT22_LOG_INTERVAL_MIN="$OLD_INT"
    return 0
  fi
  DHT22_NAME="$tmp"

  if [ "$DHT22_ENABLED" = "True" ]; then
    tmp=$(whiptail --title "$title" --inputbox "$q_gpio" 10 70 "$DHT22_GPIO_BCM" 3>&1 1>&2 2>&3)
    rc=$?
    if [ $rc -ne 0 ]; then
      DHT22_ENABLED="$OLD_ENABLED"
      DHT22_NAME="$OLD_NAME"
      DHT22_GPIO_BCM="$OLD_GPIO"
      DHT22_RETRIES="$OLD_RET"
      DHT22_RETRY_DELAY="$OLD_DEL"
      DHT22_OVERLAY="$OLD_OV"
      DHT22_LOG_INTERVAL_MIN="$OLD_INT"
      return 0
    fi
    DHT22_GPIO_BCM="$tmp"

    tmp=$(whiptail --title "$title" --inputbox "$q_ret" 10 70 "$DHT22_RETRIES" 3>&1 1>&2 2>&3)
    rc=$?
    if [ $rc -ne 0 ]; then
      DHT22_ENABLED="$OLD_ENABLED"
      DHT22_NAME="$OLD_NAME"
      DHT22_GPIO_BCM="$OLD_GPIO"
      DHT22_RETRIES="$OLD_RET"
      DHT22_RETRY_DELAY="$OLD_DEL"
      DHT22_OVERLAY="$OLD_OV"
      DHT22_LOG_INTERVAL_MIN="$OLD_INT"
      return 0
    fi
    DHT22_RETRIES="$tmp"

    tmp=$(whiptail --title "$title" --inputbox "$q_delay" 10 70 "$DHT22_RETRY_DELAY" 3>&1 1>&2 2>&3)
    rc=$?
    if [ $rc -ne 0 ]; then
      DHT22_ENABLED="$OLD_ENABLED"
      DHT22_NAME="$OLD_NAME"
      DHT22_GPIO_BCM="$OLD_GPIO"
      DHT22_RETRIES="$OLD_RET"
      DHT22_RETRY_DELAY="$OLD_DEL"
      DHT22_OVERLAY="$OLD_OV"
      DHT22_LOG_INTERVAL_MIN="$OLD_INT"
      return 0
    fi
    DHT22_RETRY_DELAY="${tmp//,/.}"

    whiptail --title "$title" --yesno "$q_ov" 10 70
    rc=$?
    if [ $rc -eq 0 ]; then
      DHT22_OVERLAY="True"
    elif [ $rc -eq 1 ]; then
      DHT22_OVERLAY="False"
    else
      DHT22_ENABLED="$OLD_ENABLED"
      DHT22_NAME="$OLD_NAME"
      DHT22_GPIO_BCM="$OLD_GPIO"
      DHT22_RETRIES="$OLD_RET"
      DHT22_RETRY_DELAY="$OLD_DEL"
      DHT22_OVERLAY="$OLD_OV"
      DHT22_LOG_INTERVAL_MIN="$OLD_INT"
      return 0
    fi

    tmp=$(whiptail --title "$title" --inputbox "$q_int" 10 70 "$DHT22_LOG_INTERVAL_MIN" 3>&1 1>&2 2>&3)
    rc=$?
    if [ $rc -ne 0 ]; then
      DHT22_ENABLED="$OLD_ENABLED"
      DHT22_NAME="$OLD_NAME"
      DHT22_GPIO_BCM="$OLD_GPIO"
      DHT22_RETRIES="$OLD_RET"
      DHT22_RETRY_DELAY="$OLD_DEL"
      DHT22_OVERLAY="$OLD_OV"
      DHT22_LOG_INTERVAL_MIN="$OLD_INT"
      return 0
    fi
    DHT22_LOG_INTERVAL_MIN="$tmp"
  fi
}

sensors_menu() {
  local tb mp back_label
  if [ "$LANG_CODE" = "de" ]; then
    tb="Sensoren"
    mp="Bitte einen Sensor wählen:"
    back_label="Zurück"
  else
    tb="Sensors"
    mp="Please choose a sensor:"
    back_label="Back"
  fi

  while true; do
    local s_bme s_ds s_mlx s_tsl s_d11 s_d22
    s_bme=$(bool_to_status "$BME280_ENABLED")
    s_ds=$(bool_to_status "$DS18B20_ENABLED")
    s_mlx=$(bool_to_status "$MLX90614_ENABLED")
    s_tsl=$(bool_to_status "$TSL2591_ENABLED")
    s_d11=$(bool_to_status "$DHT11_ENABLED")
    s_d22=$(bool_to_status "$DHT22_ENABLED")

    CHOICE=$(whiptail --title "$tb" --menu "$mp" 20 70 10 \
      "1" "BME280  ($s_bme)" \
      "2" "DS18B20 ($s_ds)" \
      "3" "MLX90614 ($s_mlx)" \
      "4" "TSL2591 ($s_tsl)" \
      "5" "DHT11  ($s_d11)" \
      "6" "DHT22  ($s_d22)" \
      "Z" "$back_label" \
      3>&1 1>&2 2>&3) || return 0

    case "$CHOICE" in
      "1") edit_bme280 ;;
      "2") edit_ds18b20 ;;
      "3") edit_mlx90614 ;;
      "4") edit_tsl2591 ;;
      "5") edit_dht11 ;;
      "6") edit_dht22 ;;
      "Z") return 0 ;;
    esac
  done
}

# ---------------------------------------------------
# Andere Optionen: KPINDEX, ANALEMMA, SQM
# ---------------------------------------------------
edit_kpindex() {
  local title q_enable q_ov q_int rc tmp
  if [ "$LANG_CODE" = "de" ]; then
    title="Kp-Index"
    q_enable="Kp-Index-Auswertung aktivieren?"
    q_ov="Kp-Index im Bild anzeigen (Overlay)?"
    q_int="Logger-Intervall in Minuten (Cronjob-Frequenz, z.B. 5):"
  else
    title="Kp index"
    q_enable="Enable Kp index feature?"
    q_ov="Show Kp index as overlay on image?"
    q_int="Logger interval in minutes (cronjob frequency, e.g. 5):"
  fi

  local OLD_EN="$KPINDEX_ENABLED"
  local OLD_OV="$KPINDEX_OVERLAY"
  local OLD_INT="$KPINDEX_LOG_INTERVAL_MIN"

  # Aktivieren / deaktivieren
  whiptail --title "$title" --yesno "$q_enable" 10 70
  rc=$?
  if [ $rc -eq 0 ]; then
    KPINDEX_ENABLED="True"
  elif [ $rc -eq 1 ]; then
    KPINDEX_ENABLED="False"
  else
    KPINDEX_ENABLED="$OLD_EN"
    return 0
  fi

  # Wenn nicht aktiviert: Overlay/Intervall erstmal in Ruhe lassen
  if [ "$KPINDEX_ENABLED" != "True" ]; then
    return 0
  fi

  # Overlay
  whiptail --title "$title" --yesno "$q_ov" 10 70
  rc=$?
  if [ $rc -eq 0 ]; then
    KPINDEX_OVERLAY="True"
  elif [ $rc -eq 1 ]; then
    KPINDEX_OVERLAY="False"
  else
    KPINDEX_ENABLED="$OLD_EN"
    KPINDEX_OVERLAY="$OLD_OV"
    KPINDEX_LOG_INTERVAL_MIN="$OLD_INT"
    return 0
  fi

  # Intervall in Minuten
  tmp=$(whiptail --title "$title" --inputbox "$q_int" 10 70 "$KPINDEX_LOG_INTERVAL_MIN" 3>&1 1>&2 2>&3)
  rc=$?
  if [ $rc -ne 0 ]; then
    KPINDEX_ENABLED="$OLD_EN"
    KPINDEX_OVERLAY="$OLD_OV"
    KPINDEX_LOG_INTERVAL_MIN="$OLD_INT"
    return 0
  fi
  KPINDEX_LOG_INTERVAL_MIN="$tmp"
}

edit_analemma() {
  local title q_enable q_shut q_gain q_bri q_con q_sat rc tmp
  if [ "$LANG_CODE" = "de" ]; then
    title="Analemma"
    q_enable="Analemma-Berechnung aktivieren?"
    q_shut="Belichtungszeit A_SHUTTER (ms, z.B. 10):"
    q_gain="Gain A_GAIN (z.B. 1.0):"
    q_bri="Helligkeit A_BRIGHTNESS (z.B. 0.0):"
    q_con="Kontrast A_CONTRAST (z.B. 0.0):"
    q_sat="Sättigung A_SATURATION (z.B. 0.0):"
  else
    title="Analemma"
    q_enable="Enable analemma mode?"
    q_shut="Exposure A_SHUTTER in ms (e.g. 10):"
    q_gain="Gain A_GAIN (e.g. 1.0):"
    q_bri="Brightness A_BRIGHTNESS (e.g. 0.0):"
    q_con="Contrast A_CONTRAST (e.g. 0.0):"
    q_sat="Saturation A_SATURATION (e.g. 0.0):"
  fi

  local OLD_EN="$ANALEMMA_ENABLED"
  local OLD_SH="$A_SHUTTER"
  local OLD_GN="$A_GAIN"
  local OLD_BR="$A_BRIGHTNESS"
  local OLD_CO="$A_CONTRAST"
  local OLD_SA="$A_SATURATION"

  whiptail --title "$title" --yesno "$q_enable" 10 70
  rc=$?
  if [ $rc -eq 0 ]; then
    ANALEMMA_ENABLED="True"
  elif [ $rc -eq 1 ]; then
    ANALEMMA_ENABLED="False"
  else
    ANALEMMA_ENABLED="$OLD_EN"
    return 0
  fi

  if [ "$ANALEMMA_ENABLED" = "True" ]; then
    tmp=$(whiptail --title "$title" --inputbox "$q_shut" 10 70 "$A_SHUTTER" 3>&1 1>&2 2>&3)
    rc=$?; [ $rc -ne 0 ] && {
      ANALEMMA_ENABLED="$OLD_EN"
      A_SHUTTER="$OLD_SH"; A_GAIN="$OLD_GN"; A_BRIGHTNESS="$OLD_BR"; A_CONTRAST="$OLD_CO"; A_SATURATION="$OLD_SA"
      return 0; }
    A_SHUTTER="$tmp"

    tmp=$(whiptail --title "$title" --inputbox "$q_gain" 10 70 "$A_GAIN" 3>&1 1>&2 2>&3)
    rc=$?; [ $rc -ne 0 ] && {
      ANALEMMA_ENABLED="$OLD_EN"
      A_SHUTTER="$OLD_SH"; A_GAIN="$OLD_GN"; A_BRIGHTNESS="$OLD_BR"; A_CONTRAST="$OLD_CO"; A_SATURATION="$OLD_SA"
      return 0; }
    A_GAIN="${tmp//,/.}"

    tmp=$(whiptail --title "$title" --inputbox "$q_bri" 10 70 "$A_BRIGHTNESS" 3>&1 1>&2 2>&3)
    rc=$?; [ $rc -ne 0 ] && {
      ANALEMMA_ENABLED="$OLD_EN"
      A_SHUTTER="$OLD_SH"; A_GAIN="$OLD_GN"; A_BRIGHTNESS="$OLD_BR"; A_CONTRAST="$OLD_CO"; A_SATURATION="$OLD_SA"
      return 0; }
    A_BRIGHTNESS="${tmp//,/.}"

    tmp=$(whiptail --title "$title" --inputbox "$q_con" 10 70 "$A_CONTRAST" 3>&1 1>&2 2>&3)
    rc=$?; [ $rc -ne 0 ] && {
      ANALEMMA_ENABLED="$OLD_EN"
      A_SHUTTER="$OLD_SH"; A_GAIN="$OLD_GN"; A_BRIGHTNESS="$OLD_BR"; A_CONTRAST="$OLD_CO"; A_SATURATION="$OLD_SA"
      return 0; }
    A_CONTRAST="${tmp//,/.}"

    tmp=$(whiptail --title "$title" --inputbox "$q_sat" 10 70 "$A_SATURATION" 3>&1 1>&2 2>&3)
    rc=$?; [ $rc -ne 0 ] && {
      ANALEMMA_ENABLED="$OLD_EN"
      A_SHUTTER="$OLD_SH"; A_GAIN="$OLD_GN"; A_BRIGHTNESS="$OLD_BR"; A_CONTRAST="$OLD_CO"; A_SATURATION="$OLD_SA"
      return 0; }
    A_SATURATION="${tmp//,/.}"
  fi
}

edit_sqm() {
  local title q_zp q_patch rc tmp
  if [ "$LANG_CODE" = "de" ]; then
    title="SQM / Photometrie"
    q_zp="Zero-Point ZP (z.B. 6.0):"
    q_patch="SQM_PATCH_SIZE (Pixelgröße des Patches, z.B. 100):"
  else
    title="SQM / photometry"
    q_zp="Zero point ZP (e.g. 6.0):"
    q_patch="SQM_PATCH_SIZE (patch size in pixels, e.g. 100):"
  fi

  local OLD_ZP="$ZP"
  local OLD_PA="$SQM_PATCH_SIZE"

  tmp=$(whiptail --title "$title" --inputbox "$q_zp" 10 70 "$ZP" 3>&1 1>&2 2>&3)
  rc=$?; [ $rc -ne 0 ] && return 0
  ZP="${tmp//,/.}"

  tmp=$(whiptail --title "$title" --inputbox "$q_patch" 10 70 "$SQM_PATCH_SIZE" 3>&1 1>&2 2>&3)
  rc=$?
  if [ $rc -ne 0 ]; then
    ZP="$OLD_ZP"
    SQM_PATCH_SIZE="$OLD_PA"
    return 0
  fi
  SQM_PATCH_SIZE="$tmp"
}

other_options_menu() {
  local tb mp back_label s_kp s_an s_sqm
  if [ "$LANG_CODE" = "de" ]; then
    tb="Andere Optionen"
    mp="Bitte eine Option wählen:"
    back_label="Zurück"
  else
    tb="Other options"
    mp="Please choose an option:"
    back_label="Back"
  fi

  while true; do
    s_kp=$(bool_to_status "$KPINDEX_ENABLED")
    s_an=$(bool_to_status "$ANALEMMA_ENABLED")
    s_sqm="ZP=${ZP}, Patch=${SQM_PATCH_SIZE}"

    CHOICE=$(whiptail --title "$tb" --menu "$mp" 20 70 10 \
      "1" "KPINDEX  ($s_kp)" \
      "2" "ANALEMMA ($s_an)" \
      "3" "SQM      ($s_sqm)" \
      "Z" "$back_label" \
      3>&1 1>&2 2>&3) || return 0

    case "$CHOICE" in
      "1") edit_kpindex ;;
      "2") edit_analemma ;;
      "3") edit_sqm ;;
      "Z") return 0 ;;
    esac
  done
}

# ---------------------------------------------------
# Prozesse (Cronjobs) – Info
# ---------------------------------------------------
show_processes() {
  local title msg
  if [ "$LANG_CODE" = "de" ]; then
    title="Prozesse (Cronjobs)"
    msg="Die Sensor-Logger-Cronjobs werden automatisch nach Sensor-Status und Intervall erzeugt.\n\n\
Basisjobs:\n\
- Allsky Raspi-Status (*/1 Min)\n\
- Config Update (täglich 12:00)\n\
- Nightly FTP-Upload (täglich 08:45)\n\
- SQM Messung (alle 5 Min)\n\
- SQM Plot Generierung (täglich 08:00)\n\n\
Sensor-Logger hängen von den *_ENABLED-Flags und *_LOG_INTERVAL_MIN in config.py ab."
  else
    title="Processes (cronjobs)"
    msg="Sensor logger cronjobs are generated automatically based on sensor status and interval.\n\n\
Base jobs:\n\
- Allsky Raspi status (*/1 min)\n\
- Config update (daily 12:00)\n\
- Nightly FTP upload (daily 08:45)\n\
- SQM measurement (every 5 min)\n\
- SQM plot generation (daily 08:00)\n\n\
Sensor loggers depend on *_ENABLED flags and *_LOG_INTERVAL_MIN in config.py."
  fi
  whiptail --title "$title" --msgbox "$msg" 20 80
}

# ---------------------------------------------------
# Hauptmenü
# ---------------------------------------------------
while true; do
  if [ "$LANG_CODE" = "de" ]; then
    MTITLE="AllSkyKamera Konfiguration"
    MPROMPT="Bitte einen Bereich wählen:"
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

TSL2591_ENABLED        = ${TSL2591_ENABLED}
TSL2591_NAME           = "${TSL2591_NAME_ESC}"
TSL2591_I2C_ADDRESS    = ${TSL2591_I2C_ADDRESS}
TSL2591_SQM2_LIMIT     = ${TSL2591_SQM2_LIMIT}
TSL2591_SQM_CORRECTION = ${TSL2591_SQM_CORRECTION}
TSL2591_OVERLAY        = ${TSL2591_OVERLAY}

DS18B20_ENABLED  = ${DS18B20_ENABLED}
DS18B20_NAME     = "${DS18B20_NAME_ESC}"
DS18B20_OVERLAY  = ${DS18B20_OVERLAY}

# DHT11
DHT11_ENABLED      = ${DHT11_ENABLED}
DHT11_NAME         = "${DHT11_NAME_ESC}"
DHT11_GPIO_BCM     = ${DHT11_GPIO_BCM}
DHT11_RETRIES      = ${DHT11_RETRIES}
DHT11_RETRY_DELAY  = ${DHT11_RETRY_DELAY}
DHT11_OVERLAY      = ${DHT11_OVERLAY}

# DHT22
DHT22_ENABLED      = ${DHT22_ENABLED}
DHT22_NAME         = "${DHT22_NAME_ESC}"
DHT22_GPIO_BCM     = ${DHT22_GPIO_BCM}
DHT22_RETRIES      = ${DHT22_RETRIES}
DHT22_RETRY_DELAY  = ${DHT22_RETRY_DELAY}
DHT22_OVERLAY      = ${DHT22_OVERLAY}

MLX90614_ENABLED     = ${MLX90614_ENABLED}
MLX90614_NAME        = "${MLX90614_NAME_ESC}"
MLX90614_I2C_ADDRESS = ${MLX90614_I2C_ADDRESS}

# Logger-Intervalle in Minuten
BME280_LOG_INTERVAL_MIN   = ${BME280_LOG_INTERVAL_MIN}
TSL2591_LOG_INTERVAL_MIN  = ${TSL2591_LOG_INTERVAL_MIN}
DS18B20_LOG_INTERVAL_MIN  = ${DS18B20_LOG_INTERVAL_MIN}
DHT11_LOG_INTERVAL_MIN    = ${DHT11_LOG_INTERVAL_MIN}
DHT22_LOG_INTERVAL_MIN    = ${DHT22_LOG_INTERVAL_MIN}
MLX90614_LOG_INTERVAL_MIN = ${MLX90614_LOG_INTERVAL_MIN}

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
    whiptail --title "Upload erfolgreich" --msgbox "Die Konfiguration wurde erfolgreich auf den Server übertragen." 8 70
  else
    whiptail --title "Upload successful" --msgbox "Configuration has been successfully uploaded to the server." 8 70
  fi

  if python3 -m scripts.manage_crontabs; then
    if [ "$LANG_CODE" = "de" ]; then
      whiptail --title "Cronjobs aktualisiert" --msgbox "Die Crontab-Einträge für die Sensor-Logger wurden erfolgreich aktualisiert." 8 70
    else
      whiptail --title "Cronjobs updated" --msgbox "Crontab entries for sensor loggers have been updated successfully." 8 70
    fi
  else
    if [ "$LANG_CODE" = "de" ]; then
      whiptail --title "Fehler bei Cronjobs" --msgbox "Die Crontab-Einträge konnten nicht automatisch aktualisiert werden.\nBitte prüfen Sie die Logs oder führen Sie den Befehl manuell aus:\n\npython3 -m scripts.manage_crontabs" 12 80
    else
      whiptail --title "Cronjob update failed" --msgbox "Crontab entries could not be updated automatically.\nPlease check the logs or run manually:\n\npython3 -m scripts.manage_crontabs" 12 80
    fi
  fi

else
  if [ "$LANG_CODE" = "de" ]; then
    whiptail --title "Fehler beim Upload" --msgbox "Das Python-Skript konnte nicht erfolgreich ausgeführt werden.\nBitte prüfen Sie die Logs oder führen Sie den Upload manuell aus:\n\npython3 -m scripts.upload_config_json" 12 80
  else
    whiptail --title "Upload failed" --msgbox "The Python script failed to run.\nPlease check the logs or run manually:\n\npython3 -m scripts.upload_config_json" 12 80
  fi
fi
