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

# Update
Für alle die meine Python-Bibliothek schon installiert haben, ist es sinnvoll ab und an die Bibliothek zu aktualisieren. Wir programmieren ständig an den Funktionalitäten.

Der Update geht ebenso einfach wie die Installation.
1. Man muss sich auf seiner Raspberry Pi einloggen.
2. Im Terminal führt man folgende beiden Befehle aus:
   <code>
   cd AllSkyKamera
   git pull
   </code>

Beim Update werden keine config-Einstellungen überschrieben. 
Es werdenb lediglich die angepassten Funktionen aktualisiert.

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

Folgende Abfragen erfolgen mit der Installation:
- Haben Sie bereits einen API-Key? (y/n)
- API_KEY:
  Der API-Key oder Secret-Key wird abgefragt und gleich auf dem Server getestet. Gibt es diesen nicht, bricht die Installation ab. 
Existiert ein Key, gibt die Funktion die Kamera-ID (e.g. ASK001) zurück
- Pfad zum Interface:
  Hier gibt man den Pfad zum Allsky-Interface an. Meisten liegt dieser unter /home/<user>/allsky (e.g. /home/pi/allsky)
- Name der Kamera (z.B. Meine AllskyCam):
- Name des Standortes (z.B. Berliner Sternwarte):
- Benutzername (z.B. Tom Mustermann):
- E-Mailadresse:
- Webseite (optional):

<strong>ACHTUNG</strong> Gibt man die Standort-Daten sehr genau an, sieht man auf der Karte auch den sehr genauen Standort. Wer das nicht möchte, kann die Standort-Daten zu Länge und Breite einfach etwas verschieben. 

- Breitengrad des Standortes (z.B. 52.1253):
- Längengrad des Standortes (z.B. 13.1245):  
- Pixelgröße des Kamerachips in mm (z.B. 0.00155):
- Brennweite in mm (z.B. 1.85):
- Nullpunkt Helligkeit ZP (Default: 6.0):

 Falls Sensoren wie BME280, DS18b20 oder ein TSL2591 vorhanden ist, kann hier die Einstellungen vornehmen.
 Ansonsten nicht, kann hier einfach ein n eingetragen werden:
 - BME280 verwenden? (y/n):
    - I2C-Adresse BME280 (z.B. 0x76):
    - BME280_Overlay anlegen? (y/n):
 - TSL2591 verwenden? (y/n):
    - I2C-Adresse TSL2591 (z.B. 0x29):
    - SQM2-Limit (z.B. 6.0):
    - SQM-Korrekturwert (z.B. 0.0):
    - TSL2591_Overlay anlegen? (y/n):
  - DS18B20 verwenden? (y/n):
    - DS18B20_Overlay anlegen? (y/n):

Anschließend werden noch einige Tests durchgeführt und die Installation ist beendet.
Nach der Installation befindet sich die generierte Konfigurationsdatei unter ~/AllSkyKamera/askutils/config.py

Der letzte Schritt ist die Übertragung der configuration an den Server. Sobald dies erfolgt ist, ist auf der Webseite die Kamera sichtbar.

Nach der Installtion muss die Kamera, das Interface oder die Rapsberry Pi <strong>nicht</strong> neu gestartet werden. Sobald die Conjobs eingetragen sind, startet die Übertragung.
Sollte auf der Webseite nichts erscheinen, wurde die configuration nicht übertragen oder die Cronjobs laufen noch nicht.

# Cronjobs

Die Bibliothek arbeitet mit cronjobs. Diese cronjobs werden in den crontab eingetragen und sind damit für den Usern auch jederzeit einsehbar oder auch änderbar.

Die crontabs werden bei der Installation in der config.py eingetragen. Um diese zu aktivieren ist der folgende Aufruf nötig:
<code>
cd
cd AllSkyKamera
python3 -m scripts.manage_crontabs
</code>

Jetzt wird die config.py ausgelesen und alle dort definierten cronjobs werden in den crontab eingetragen.
Hat dies funktioniert, sollte innerhalb einer Minute die Kamera die Daten an den Server senden und diese erscheinen dann auf der Netzwerk-Seite: https://allskykamera.space

Sollte die Kamera noch nicht auf der Webseite stehen, muss die config.py noch an den Server übertragen werden. Das geht einfach mit:
<code>
cd ~/AllSkyKamera
python3 -m scripts.upload_config_json
</code>

Anschließend ist die Kamera auf der Webseite zu sehen.

# Testen der Sensoren und Skripte

Um Unterverzeichnis AllSkyKamera/tests gibt es verschiedene Skripte zum Testen der Bibliothek. Dabei werden keine Daten auf den Server geschoben, sondern ausschließlich die Funktion gestetet.

Alle Skripte können direkt aufgerufen werden. Dazu wechselt man in das Verzeichnis tests und ruft mit python3 die Skripte auf. Die Ausgaben zeigen dann die Funktion der Skripte.

<strong>bme280_test.py</strong><br>
Testen des Sensor BME280.<br>
Beschreibung: Sensor für Temperatur, Luftfeuchtigkeit, Luftdruck (i²c-Schnittstelle)<br>
Aufruf: <code>python3 bme280_test.py</code><br>
Typische Ausgabe ist:<br>
<code>
🌡️ Temperatur : 34.21 °C
🧭 Druck      : 1015.20 hPa
💧 Feuchte    : 32.15 %
❄️ Taupunkt   : 15.23 °C
</code>

<strong>ds18b20_test.py</strong><br>
Testen des Sensor DS18B20.<br>
Beschreibung: Temperatursensor (1-Wire-Schnittstelle) für Aussentemperaturmessungen.<br>
Aufruf: <code>python3 ds18b20_test.py</code><br>
Typische Ausgabe ist:<br>
<code>
🌡️ Temperatur: 30.44 °C
🌡️ Temperatur: 30.44 °C
🌡️ Temperatur: 30.50 °C
...
</code>
Das Skript muss mit STRG+C abgebrochen werden, sonst läuft es durchgängig weiter.

<strong>tsl2591_test.py</strong><br>
Testen des Sensor TSL2591.<br>
Beschreibung: Lichtsensor zur Messung der Heligkeit<br>
Aufruf: <code>python3 tsl2591_test.py</code><br>
Typische Ausgabe ist:<br>
<code>
</code>
Dieser Sensor wird aktuell in keiner meiner Kameras verwendet. Sobald ich diesen wieder verbaue, werde ich Dokumentation hier nachziehen.

<strong>FTP-Test</strong><br>
Die Bibliothek schiebt die Daten wie Bilder, Videos, Keogramme über die FTP-Schnittstelle.
Diese kann man hier testen.
Aufruf: <code>python3 ftp_upload_test.py</code><br>
Typische Ausgabe ist:<br>
<code>
== 1. Teste Konfiguration ==
✅ Konfigurationswerte sind vorhanden.

== 2. Teste FTP-Verbindung ==
✅ FTP-Login erfolgreich bei h2888788.stratoserver.net.
✅ Wechsel ins Remote-Verzeichnis 'ASK005' erfolgreich.
ℹ️ Aktueller Verzeichnisinhalt: ['config.json', 'image.jpg', 'keogram', 'sqm', 'startrails', 'videos']

== 3. Teste image_upload-Funktion ==
ℹ️ Testdatei erstellt: /home/pi/allsky/tmp/test_upload.txt
✅ Upload abgeschlossen: test_upload.txt → /ASK005
✅ upload_image() erfolgreich.
ℹ️ Testdatei remote gelöscht: test_upload.txt

✅ Alle FTP-Tests erfolgreich abgeschlossen.
</code>

<strong>SQM-Test</strong><br>
Aktuelle teste ich die Möglichkeit aus den Bild-Daten die Himmelshelligkeit zu berechnen.
Der SQM-Test greift dabei auf die Bilddaten zu und berechnet die aktuelle Helligkeit. Berücksichtig werden dabei auch Belichtungszeit (exposure-time) und Empfindlichkeit (Gain).<br>
Aufruf: <code>python3 sqm_test.py</code><br>
Typische Ausgabe ist:<br>
<code>
2025-08-09 13:36:25+02:00 -> μ = 1.77 mag/arcsec², Gain=1.379, Exptime=0.000142s gespeichert in 
</code>

# Funktionen der Bibliothek

An dieser Stelle werden die Funktionen der Bibliothek dokumentiert. 
Alle Bibliotheksfunktionen sind über Cronjobs gesteuert und können daher auch einzeln aufgerufen werden.
Der Aufruf der Funktion dient dem debugging und dem prüfen ob alle Funktionen funktionieren und die Daten auch an den Server gesendet werden.

Alle Aufrufe der Bibliotheksfunktionen erfolgen aus dem Hauptverzeichnis.
Man kann mit folgendem Befehl ins Hauptverzeichnis wechseln.
<code>
cd ~\AllSkyKamera
</code>

## manage_crontabs
<br>**Beschreibung:**
<br>Liest alle definierten cronjobs aus der **config.py** und trägt diese in die crontabs ein.
Sollten gleichnamige crontabs schon existieren, werden diese gemäß der config geändert.
Bestehende andere crontabs werden dabei nicht angefasst oder geändert.
<br>**Aufruf:**
<br><code>
python3 -m scripts.manage_crontabs
</code>
<br>**Cronjob:**
<br>Es ist nicht nötig ständig diese Datei aufzurufen. Daher braucht es für diese Funktion keinen cronjob.
Wurde in der config.py ein cronjob neu definiert oder geändert, reicht 1 Aufruf dieser Funktion. 

## upload_config_json
<br>**Beschreibung:**
<br>Die config.py ist die zentrale Einstellungsdatei.
Damit Änderungen auch auf der Webseite des Netzwerkes ankommen, wird die config.py übersetzt in eine minimale JSON-Datei und auf den Server übertragen, so das die Webseite Aktualisierungen beim Namen der Kamera oder bei Benutzereinstellungen anzeigen kann.
<br>**Aufruf:**
<br><code>
python3 -m scripts.upload_config_json
</code>
<br>**Cronjob:**
<br>Diese Funktion sollte 1mal am Tag ausgeführt werden. Das gewährleistet die Aktualität der lokalen Kamera und der Webseite.
<br>**config.py:**
<br>Hier ein Beispiel aus der config.py:
<br><code>
    {
        "comment": "Config Update",
        "schedule": "0 12 * * *",
        "command": "cd /home/pi/AllSkyKamera && python3 -m scripts.upload_config_json"
    },
</code>

## run_image_upload
<br>**Beschreibung:**
<br>Dieses Module kümmert sich um den Upload des aktuellen Kamera-Bildes.
<br>Diese Funktion ist zwingend notwendig für die Teilnahme am Netzwerk.
<br>**Aufruf:**
<br><code>
python3 -m scripts.run_image_upload
</code>
<br>**Cronjob:**
<br>Diese Funktion sollte 2x pro Minute aufgerufen werden, damit regelmäßig die aktuelle Ansicht auf der Webseite erscheint.
<br>**config.py:**
<br>Hier ein Beispiel aus der config.py:
<br><code>
   {
       "comment": "Image FTP-Upload",
       "schedule": "*/2 * * * *",
       "command": "cd /home/pi/AllSkyKamera && python3 -m scripts.run_image_upload"
   },
</code>

##run_nightly_upload
<br>**Beschreibung:**
<br>Dieses Module kümmert sich um den Upload der Sorucen aus der letzten Nacht.
Hierbei werden das Zeitraffer-Video, das Keogram und das Startrail der letzten Nacht auf den Server geladen.
Diese Funktion ist zwingend notwendig für die Teilnahme am Netzwerk.
<br>**Aufruf:**
<br><code>
python3 -m scripts.run_nightly_upload
</code>
<br>**Cronjob:**
<br>Diese Funktion muss 1x am Tag aufgerufen werden.
Der Aufruf sollte immer nach Sonnenaufgang erfolgen, da dann die entsprechenden Videos, Startrails und Keogramme erfolgreich erstellt wurden.
<br>**config.py:**
<br>Hier ein Beispiel aus der config.py:
<br><code>
   {
       "comment": "Nightly FTP-Upload",
        "schedule": "30 7 * * *",
        "command": "cd /home/pi/AllSkyKamera && python3 -m scripts.run_nightly_upload"
   },
</code>

##raspi_status
<br>**Beschreibung:**
<br>Dieses Modul überträgt den Status der Raspberry Pi. 
Hierbei werden Werte wie Temperatur, Boottime, Speicherplatz frei/benutzt an die Datenbank gesendet und auf der Webseite dargestellt.
Weiterhin gibt dieses Modul den Online-Status an die Datenbank weiter und sorgt dafür das die Kamera als Online oder Offline auf der Webseite angezeigt wird.
Diese Funktion ist zwingend notwendig für die Teilnahme am Netzwerk.
<br>**Aufruf:**
<br><code>
python3 -m scripts.raspi_status
</code>
<br>**Cronjob:**
<br>Diese Funktion sollte in einem kurzen Intervall ausgeführt (1-2 Minuten) werden.
<br>**config.py:**
<br>Hier ein Beispiel aus der config.py:
<br><code>
   {
       "comment": "Allsky Raspi-Status",
       "schedule": "*/1 * * * *",
       "command": "cd /home/pi/AllSkyKamera && python3 -m scripts.raspi_status"
   },
</code>

# Sensorenfunktionen

##bme280_logger
<br>**Beschreibung:**
<br>Dieses Modul liest den Sensor BME280 aus und überträgt die Daten in die Datenbank.
Der Sensor selbst liefert:
- Temperatur
- Luftfeuchtigkeit
- Luftdruck
Weiterhin berechnet das Modul den Taupunkt und gibt diesen ebenfalls an die Datenbank weiter.
<br>**Aufruf:**
<br><code>
python3 -m scripts.bme280_logger
</code>
<br>**Cronjob:**
<br>Diese Funktion sollte in einem kurzen Intervall ausgeführt (1-2 Minuten) werden.
<br>**config.py:**
<br>Hier ein Beispiel aus der config.py:
<br><code>
   {
       "comment": "BME280 Sensor",
       "schedule": "*/1 * * * *",
       "command": "cd /home/pi/AllSkyKamera && python3 -m scripts.bme280_logger"
   },
</code>

##ds18b20_logger
<br>**Beschreibung:**
<br>Dieses Modul liest den Sensor DS18B20 aus und überträgt die Daten in die Datenbank.
Der Sensor selbst liefert:
- Temperatur
<br>**Aufruf:**
<br><code>
python3 -m scripts.ds18b20_logger
</code>
<br>**Cronjob:**
<br>Diese Funktion sollte in einem kurzen Intervall ausgeführt (1-2 Minuten) werden.
<br>**config.py:**
<br>Hier ein Beispiel aus der config.py:
<br><code>
   {
       "comment": "DS18B20 Sensor",
       "schedule": "*/1 * * * *",
       "command": "cd /home/pi/AllSkyKamera && python3 -m scripts.ds18b20_logger"
   },
</code>


