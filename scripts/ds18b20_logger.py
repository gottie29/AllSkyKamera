#!/usr/bin/python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from askutils import config
from askutils.sensors import ds18b20
from askutils.utils.logger import log, warn, error
from askutils.utils import influx_writer

def main():
    if not config.DS18B20_ENABLED:
        print("ℹ️ DS18B20 ist deaktiviert. Test wird übersprungen.")
        return

    try:
        temp = ds18b20.read_ds18b20()
    except Exception as e:
        error(f"❌ Fehler beim Auslesen des DS18B20: {e}")
        return

    print(f"📍 Standort: {config.STANDORT_NAME} ({config.KAMERA_ID})")
    print(f"🌡️ Temperatur: {temp:.2f} °C")

    influx_writer.log_metric("ds18b20", {
        "temp": float(temp)
    }, tags={"host": "host1"})

if __name__ == "__main__":
    main()
