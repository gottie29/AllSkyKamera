# AllSkyKamera
 Bibliothek für Python Allsky Kamera auf RaspberryPi

---

# Installation der askutils

## Repository klonen
git clone git@github.com:gottie29/AllSkyKamera.git
cd AllSkyKamera

## Python-Abhängigkeiten installieren
pip install -r requirements.txt

## Individuelle Zugangsdaten setzen
cp askutils/ASKsecret.example.py askutils/ASKsecret.py
nano askutils/ASKsecret.py   # API_KEY eintragen

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
