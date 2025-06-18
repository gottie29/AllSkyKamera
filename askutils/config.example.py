# Konfiguration der Kamera
# config.py


try:
    from askutils.ASKsecret import API_KEY, API_URL
except ImportError:
    print("❌ Datei 'ASKsecret.py' fehlt oder ist ungültig!")
    API_KEY = API_URL = None

####################################################################
# Benutzereinstellungen vornehmen
####################################################################
# 📍 Kamera-Standort
KAMERA_ID = "e.g. ASK001" # muss zum Secret passen
KAMERA_NAME = "e.g. meine Kamera"
STANDORT_NAME = "e.g. mein Standort"
BENUTZER_NAME = "e.g. mein Name"
KONTAKT_EMAIL = "e.g. meine E-Mail"
LATITUDE = 52.239988 # ACHTUNG sehr genau, am besten nicht auf den eigenen Standort direkt setzen
LONGITUDE = 13.432869 # ACHTUNG sehr genau, am besten nicht auf den eigenen Standort direkt setzen

###########################################################
# Sensoren
###########################################################
# BME280-Konfiguration  
###########################################################
# BME280 ist ein Umweltsensor, der Temperatur, Luftfeuchtigkeit und Luftdruck misst.
# Er wird über I2C angesprochen und benötigt die Adresse 0x76
# Standardmäßig ist der Sensor aktiviert, du kannst ihn aber deaktivieren, wenn du ihn nicht verwendest.
# Wenn du den Sensor deaktivierst, werden keine Messwerte in die Datenbank geschrieben
# und die entsprechenden Grafiken werden nicht erstellt.
BME280_ENABLED = True
BME280_I2C_ADDRESS = 0x76

############################################################
# TSL2591-Konfiguration
############################################################
# TSL2591 ist ein Lichtsensor, der Helligkeit in Lux misst.
# Er wird ebenfalls über I2C angesprochen und benötigt die Adresse 0x29
# Standardmäßig ist der Sensor aktiviert, du kannst ihn aber deaktivieren, wenn du ihn nicht verwendest.
# Wenn du den Sensor deaktivierst, werden keine Messwerte in die Datenbank geschrieben
TSL2591_ENABLED = True
TSL2591_I2C_ADDRESS = 0x29  # Standardadresse
TSL2591_SQM2_LIMIT = 6.0    # unterhalb wird SQM2 auf 0.0001 gesetzt
TSL2591_SQM_CORRECTION = 0.0  # Kalibrierwert in mag/arcsec²

############################################################
# DHT11-Konfiguration
############################################################
# DHT11 ist ein einfacher Temperatursensor, der Temperatur und Luftfeuchtigkeit misst
# Er wird über GPIO angesprochen und benötigt einen freien GPIO-Pin
# Standardmäßig ist der Sensor aktiviert, du kannst ihn aber deaktivieren, wenn du ihn nicht verwendest.
# Wenn du den Sensor deaktivierst, werden keine Messwerte in die Datenbank geschrieben
# und die entsprechenden Grafiken werden nicht erstellt.
DHT11_ENABLED = True
DHT11_GPIO = 4  # z. B. GPIO 4 (physisch Pin 7)



###########################################################
# 📁 Pfade
###########################################################
IMAGE_BASE_PATH = "/home/pi/allsky/images"
SCRIPTS_PATH = "/home/pi/scripts4"
LOG_PATH = f"{SCRIPTS_PATH}/logs"

################### CRONTABS ###################################
# Eintragen lassen mit dem Skriptaufruf
# python3 -m scripts.manage_crontabs
# im Verzeichnis AllskyKamera
################################################################
CRONTABS = [
    {
        "comment": "Allsky Raspi-Status",
        "schedule": "*/1 * * * *",  # alle 5 Minuten
        "command": "cd /home/pi/AllSkyKamera && python3 -m scripts.raspi_status"
    },
    {
        "comment": "Config Update",
        "schedule": "0 12 * * *",  #  12 Uhr Mittags
        "command": "cd /home/pi/AllSkyKamera && python3 -m scripts.upload_config_json"
    },
    # Weitere Jobs kannst du einfach ergänzen
]


###################################################################
# Nichts ändern !!!
###################################################################
FTP_VIDEO_DIR = "videos"
FTP_KEOGRAM_DIR = "keograms"
FTP_STARTRAIL_DIR = "startrails"

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
