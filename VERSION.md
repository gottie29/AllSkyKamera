Versionshistorie
----------------
# v2025.10.12_01:

## Neue Funktionen

Hier eine Übersicht über die neuen Funktionen

### Allgemeines
- die Versionsnummer wird nun mit auf den Server übertragen und auf der Webseite bei den einzelnen Kameras angezeigt
- die config.py wird auf den Server übertragen (einfacheres Debugging - kann nicht von aussen eingesehen werden)
- Einbau der Steuerung des MLX90614 Sensors in die Bibliothek (Aktivierung über sensor_config.sh)
- Einbu des Testskripts für mlx90614 unter ~/AllSkyKamera/tests/mlx90614_test.py
- DHT11 und DHT22 als Testskript eingebaut. Noch nicht in der Bibliothek implementiert

### Neues Skript: AllSkyKamera/sensor_config.sh
- Steuerung der implementierten Sensoren über ein kleines Menü
- Sensoren lassen sich damit ausschalten oder anschalten
- config.py wird damit angepasst
- cronjobs werden in der config.py damit definiert und geändert

Aufruf:
<code>
cd ~/AllSkyKamera
./sensor_config.sh
</code>

### Neues Skript: AllSkyKamera/startstop.sh
Falls die Kamera mal auf der Webseite offline gehen muss, weil z.B. gebastelt wird, kann man die Übertragung auf den Server mit diesem Skript stoppen und starten
Aufruf:
Stoppen der Übertragung:
<code>
cd ~/AllSkyKamera
./startstop.sh stop
</code>
Starten der Übertragung:
<code>
cd ~/AllSkyKamera
./startstop.sh start
</code>

## Bug fixing 
- Sonderzeichne aus allen Skripten entfernt. Nun sollte die Installation wesenlich stabiler laufen

# v2025.10.01_01:

## Neue Funktionen
- Start-Stop-Skript für die Bibliothek integriert. Damit kann man die Übertragung an den Server stoppen und wieder starten

# v2025.09.30_02:

Für diese neue Version ist eine Neuinstallation erforderlich.
Benutzt dazu bitte das uninstall.sh Skript im AllSkyKamera-Verzeichnis
Daten müssen neu eingegeben werde. Hier auch der Secret-Key.

## Neue Funktionen
- KP-Index für Overlay eingebaut
- Installation angepasst und stabilisiert
- Testskript für Relaissteuerung eingebaut

## Bug fixing 
- Installation angepasst
- Error in Overlay-Variablen behoben
- kleinere Bugfixes


# v2025.09.30_01:

Neuinstallation ist nich erforderlich.
Es reicht folgender Code für das Update:
<code>
cd ~/AllSkyKamera
git pull
</code>
Sobald eine neue Version erscheint, ist das hinfällig.

## Neue Funktionen
- Integration einer Versionsnummer - wird auch auf der Webseite angezeigt
