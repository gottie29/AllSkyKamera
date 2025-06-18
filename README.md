# AllSkyKamera
Bibliothek für Python Allsky Kamera auf Raspberry Pi
 
- Raspberry Pi 4B mit 2-4 GB RAM
- Version = Debian GNU/Linux 12 (bookworm)
- Aktuell arbeite ich mit Python 3.9 oder höher

---

# 🛠 Voraussetzungen & Installation

## 📦 Benötigte Python-Module

Das Skript zur Systemüberwachung verwendet folgende Module:

- `psutil` – Systeminformationen wie CPU, RAM, Temperatur
- `influxdb-client` – Verbindung zur InfluxDB 2.x API
- `requests` – Für den Abruf geheimer Zugangsdaten via API

## 📥 Installation auf dem Raspberry Pi

- sudo apt update
- sudo apt install python3-pip -y
- pip3 install psutil influxdb-client requests
(Systemweit mit der Option --break-system-packages)

---

# Installation der askutils

## Repository klonen
- git clone https://github.com/gottie29/AllSkyKamera.git
- cd AllSkyKamera

## Python-Abhängigkeiten installieren
pip install -r requirements.txt

## Individuelle Zugangsdaten setzen
- cp askutils/ASKsecret.example.py askutils/ASKsecret.py
- nano askutils/ASKsecret.py   # API_KEY eintragen

## Vorrausetzungen für Sensoren (nur falls vorhanden)

### Temperatursensor BME280
- Einschalten von i2c in raspi-config

### Lichtsensor TSL2591 - Adafruit TSL2591
- pip3 install adafruit-circuitpython-tsl2591
- Einschalten von i2c in raspi-config

### Temperatursensor DHT11
- pip3 install Adafruit_DHT
(Für neuer Systeme verwende:)
- pip3 install Adafruit_DHT --install-option="--force-pi" --break-system-packages


## Test: Sensor oder Funktion starten
python3 beispiel_skript.py

---

# 🔐 API-Zugriff & Kamera-Konfiguration

Einige Funktionen dieser Bibliothek (z. B. InfluxDB-Logging, FTP-Upload, Standortdefinition) erfordern einen **individuellen API-Key**, um geheime Zugangsdaten von der zentralen Plattform `allskykamera.space` abzurufen.

## 📧 API-Key erhalten

Bitte kontaktiere den Entwickler direkt per E-Mail, um einen persönlichen API-Key zu erhalten:

> **Stefan Gotthold**  
> ✉️ [gottie@web.de](mailto:gottie@web.de)

Der API-Key ist kamerabezogen und darf nicht öffentlich geteilt werden.

---

## 🔧 Lokale Konfiguration in `ASKsecret.py`

Erstelle eine Datei `ASKsecret.py` im Ordner `askutils/` mit folgendem Inhalt:

```python
# askutils/ASKsecret.py
API_KEY = "dein_api_key"
API_URL = "https://allskykamera.space/getSecrets.php"

---

# Erste Schritte

## Anpassen der config.py

## Erstellen der crontabs auf der config.py
python3 -m scripts.manage_crontabs



