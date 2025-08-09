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

# Testen der Bibliothek

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





