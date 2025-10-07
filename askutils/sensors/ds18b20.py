# askutils/sensors/ds18b20.py

import glob
import time

from .. import config

def read_ds18b20():
    if not config.DS18B20_ENABLED:
        raise RuntimeError(" DS18B20 ist in config.py deaktiviert!")

    base_dir = '/sys/bus/w1/devices/'
    device_folders = glob.glob(base_dir + '28-*')
    if not device_folders:
        raise RuntimeError(" Kein DS18B20-Sensor gefunden")

    device_file = device_folders[0] + '/w1_slave'
    try:
        with open(device_file, 'r') as f:
            lines = f.readlines()

        # CRC prüfen
        if lines[0].strip()[-3:] != 'YES':
            raise RuntimeError(" CRC-Fehler beim Lesen")

        # Temperatur extrahieren
        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
            temp_string = lines[1][equals_pos+2:]
            temperature_c = float(temp_string) / 1000.0
            return round(temperature_c, 2)

        # Unerwartetes Format
        raise RuntimeError(" Unerwartetes Fehlerformat")

    except Exception as e:
        # Weiterreichen als RuntimeError, damit Logger es auffängt
        raise RuntimeError(f"Fehler: {e}")
