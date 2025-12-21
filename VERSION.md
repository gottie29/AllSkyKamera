Version history
----------------

# v2025.12.21_01

- integrate a jitter for stable ftp upload into image_upload


# v2025.12.18_2

- delete special characters from upload scripts
- integrate webm timelapse extension into upload scripts (recommended is MP4)
- Installation with INDI path definition to change when the user has installed INDI at another position

# v2025.12.17_01

- Installation is running also on OS TRIXIE (tested with INDI-Interface)

# v2025.12.16_02

- INDI-Allsky-Integration - AllSky-Cameras with the software INDI-Allsky can now integrated into the network
- Prepare upload for INDI cameras (timelapse, startrail, keogram and current actual figure)
- Integrate the upload for startrail-timelapse (only for INDI)
- Prepare install.sh and setup.sh 

# v2025.12.12_01

- Integrate Sensor HTU21/GY-21/SHT21 into library
- Integrate Sensor SHT3x (SHT30, SHT31, SHT35) into library
- Offset variables for BME280 - Temp, Hum and Press - Dewpoint will calculated with   
  offset calculated values
- 

# v2025.12.09_01

- Easier Installation with first parameters (after installation running the setup.sh)
- Testing Script implemented for all sensors (DIR: tests/all_sensors_test.py)
- Implement manual upload for older data (Timelapse, Keogram, Startrial) (call: python3 -m scripts.run_manual_upload 20251201)
- setup.sh GUI Interface (Command line) implemented
- Integrate a cpu_heater script (as test) to run processes at the RPi with 25,50,75,100% for a specific time (seconds) (DIR: tests)
- Integrate into the raspi_status also the cmera temperature - if it possible to read this out from TJ-Interface

# v2025.10.19_02

- DHT11 und DHT22 eingebaut
- Upload-Pruefung geaendert - Dateien werden erst hochgeladen, wenn die Bearbeitung fertig ist
- sensor-config.sh angepasst an DHT11 und DHT22
- TSL-Sensor mit Gain und Exposure erweitert. Wird autoamtisch ermittelt
  
# v2025.10.12_01:

## Neue Funktionen

Hier eine uebersicht ueber die neuen Funktionen

### Allgemeines
- die Versionsnummer wird nun mit auf den Server uebertragen und auf der Webseite bei den einzelnen Kameras angezeigt
- die config.py wird auf den Server uebertragen (einfacheres Debugging - kann nicht von aussen eingesehen werden)
- Einbau der Steuerung des MLX90614 Sensors in die Bibliothek (Aktivierung ueber sensor_config.sh)
- Einbu des Testskripts fuer mlx90614 unter ~/AllSkyKamera/tests/mlx90614_test.py
- DHT11 und DHT22 als Testskript eingebaut. Noch nicht in der Bibliothek implementiert

### Neues Skript: AllSkyKamera/sensor_config.sh
- Steuerung der implementierten Sensoren ueber ein kleines Menue
- Sensoren lassen sich damit ausschalten oder anschalten
- config.py wird damit angepasst
- cronjobs werden in der config.py damit definiert und geaendert

Aufruf:
<code>
cd ~/AllSkyKamera
./sensor_config.sh
</code>

### Neues Skript: AllSkyKamera/startstop.sh
Falls die Kamera mal auf der Webseite offline gehen muss, weil z.B. gebastelt wird, kann man die uebertragung auf den Server mit diesem Skript stoppen und starten
Aufruf:
Stoppen der uebertragung:
<code>
cd ~/AllSkyKamera
./startstop.sh stop
</code>
Starten der uebertragung:
<code>
cd ~/AllSkyKamera
./startstop.sh start
</code>

## Bug fixing 
- Sonderzeichne aus allen Skripten entfernt. Nun sollte die Installation wesenlich stabiler laufen

# v2025.10.01_01:

## Neue Funktionen
- Start-Stop-Skript fuer die Bibliothek integriert. Damit kann man die uebertragung an den Server stoppen und wieder starten

# v2025.09.30_02:

Fuer diese neue Version ist eine Neuinstallation erforderlich.
Benutzt dazu bitte das uninstall.sh Skript im AllSkyKamera-Verzeichnis
Daten muessen neu eingegeben werde. Hier auch der Secret-Key.

## Neue Funktionen
- KP-Index fuer Overlay eingebaut
- Installation angepasst und stabilisiert
- Testskript fuer Relaissteuerung eingebaut

## Bug fixing 
- Installation angepasst
- Error in Overlay-Variablen behoben
- kleinere Bugfixes


# v2025.09.30_01:

Neuinstallation ist nich erforderlich.
Es reicht folgender Code fuer das Update:
<code>
cd ~/AllSkyKamera
git pull
</code>
Sobald eine neue Version erscheint, ist das hinfaellig.

## Neue Funktionen
- Integration einer Versionsnummer - wird auch auf der Webseite angezeigt
