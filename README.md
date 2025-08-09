# AllSkyKamera
Python-Bibliothek für Allsky-Kameras im Netzwerk AllSkyKamera-Netzwerk (https://allskykamera.space)
 
# Beschreibung
Das Netzwerk AllSkyKamera ist eine Sammlung von Allsky-Kameras.
Es soll einen einfachen Zugang zu den Daten liefern um z.B. Auswertungen im schulischen Umwelt zu realisieren oder aber auch einfach nur den Sternenhimmel von unterschiedlichen Standorten zu zeigen.

Die entstandene Python-Biblitohek ermöglicht es die Daten, Bilder, Videos der Kameras auf dem Server zu speichern und damit über die Seite https://allskykamera.space zur Verfügung zu stellen.

Dabei greift diese Bibliothek nicht in die Standard-Software vom allskyteam (Thomas Jaquin) ein oder verändert Einstellungen oder eigene Programmierungen auf der Kamera. 
Die Bibliothek zieht ausschließlich die Daten und speichert diese auf dem Server ab.

# 🛠 Voraussetzungen
Die Vorraussetzungen um am Netzwerk teilzunehmen sind denkbar einfach.
Man benötigt eine eigene Allsky-Kamera auf Basis einer Raspberry Pi (empfohlen 4 oder höher).
Das Interface sollte vom allskyteam (Thomas Jaquin) sein.

Das INDI-Allsky-Interface wird in Zukunft auch in die Bibliothek eingebunden. 

Um am Netzwerk teilzunehmen benötigt man einen Secret-Key. Diesen kann man im Netzwerk anmelden unter: https://www.allskykamera.space/machmit.php

Ohne diesen Secret-Key funktioniert die Bibliothek nicht und man kann seine Daten nicht hochladen.

# Installation
Die Installation der Python-Bibliothek gestaltet sich einfach.

1. Download der Bibliothek
   <code>
   cd
   git clone https://github.com/gottie29/AllSkyKamera.git
   cd AllSkyKamera
   </code>
3. Aufruf der Installation
   <code>
   ./install.sh
   </code>

Mit dem starten der Installation werden alle Pakete installiert, die zum Betrieb der Bibliothek nötig sind.
Weiterhin werden alle nötigen Informationen abgefragt.




# Testen der Bibliothek


# Funktionen der Bibliothek


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



