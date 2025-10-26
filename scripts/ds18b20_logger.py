#!/usr/bin/python3
import sys
import os
import json
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from askutils import config
from askutils.sensors import ds18b20
from askutils.utils.logger import log, warn, error
from askutils.utils import influx_writer

def main():
    if not config.DS18B20_ENABLED:
        print("DS18B20 ist deaktiviert. Test wird übersprungen.")
        return

    try:
        temp = ds18b20.read_ds18b20()
    except Exception as e:
        error(f"Fehler beim Auslesen des DS18B20: {e}")
        return

    print(f"Standort: {config.STANDORT_NAME} ({config.KAMERA_ID})")
    print(f"Temperatur: {temp:.2f} °C")

    if float(temp) < -35.0 or float(temp) > 75.0:
        warn(f"Ungültiger Temperaturwert: {temp:.2f} °C")
        return
    
    influx_writer.log_metric("ds18b20", {
        "temp": float(temp)
    }, tags={"host": "host1"})

    # Overlay schreiben, wenn aktiviert
    if config.DS18B20_OVERLAY:
        overlay_dir = os.path.join(config.ALLSKY_PATH, "config", "overlay", "extra")
        os.makedirs(overlay_dir, exist_ok=True)
        overlay_path = os.path.join(overlay_dir, "ds18b20_overlay.json")
        overlay_data = {
            "DS18B20_TEMP": {
                "value": f"{temp:.1f}",
                "format": "{:.1f}"
            }
        }
        with open(overlay_path, "w") as f:
            json.dump(overlay_data, f, indent=2)

if __name__ == "__main__":
    main()
