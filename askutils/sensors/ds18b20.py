# askutils/sensors/ds18b20.py

import glob
from .. import config

def read_ds18b20():
    if not config.DS18B20_ENABLED:
        raise RuntimeError("DS18B20 ist in config.py deaktiviert!")

    base_dir = '/sys/bus/w1/devices/'
    device_folders = glob.glob(base_dir + '28-*')
    if not device_folders:
        raise RuntimeError("Kein DS18B20-Sensor gefunden")

    device_file = device_folders[0] + '/w1_slave'

    try:
        with open(device_file, 'r') as f:
            lines = f.readlines()

        # CRC pruefen
        if not lines or len(lines) < 2 or lines[0].strip()[-3:] != 'YES':
            raise RuntimeError("CRC-Fehler beim Lesen")

        # Temperatur extrahieren
        equals_pos = lines[1].find('t=')
        if equals_pos == -1:
            raise RuntimeError("Unerwartetes Format (t= fehlt)")

        temp_string = lines[1][equals_pos + 2:].strip()
        temperature_c = float(temp_string) / 1000.0

        # --- Kalibrierung / Offset anwenden ---
        off = float(getattr(config, "DS18B20_TEMP_OFFSET_C", 0.0) or 0.0)
        temperature_c = temperature_c + off

        # --- Optional: Clamp ---
        t_min = float(getattr(config, "DS18B20_TEMP_MIN_C", -55.0) or -55.0)
        t_max = float(getattr(config, "DS18B20_TEMP_MAX_C", 125.0) or 125.0)
        if temperature_c < t_min:
            temperature_c = t_min
        elif temperature_c > t_max:
            temperature_c = t_max

        return round(temperature_c, 2)

    except Exception as e:
        raise RuntimeError(f"Fehler: {e}")
