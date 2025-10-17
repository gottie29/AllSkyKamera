# AllSkyKamera/scripts/dht22_logger.py
#!/usr/bin/env python3
import sys, os, json
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from askutils import config
from askutils.sensors import dhtxx
from askutils.utils.logger import log, warn, error
from askutils.utils import influx_writer

def main():
    if not getattr(config, "DHT22_ENABLED", False):
        print("DHT22 ist deaktiviert. Messung übersprungen.")
        return

    try:
        temp, hum = dhtxx.read_dht22()
        dew = dhtxx.calculate_dew_point(temp, hum)

        print(f"Standort: {config.STANDORT_NAME} ({config.KAMERA_ID})")
        print(f"Temperatur : {temp:.2f} °C")
        print(f"Feuchte    : {hum:.2f} %")
        print(f"Taupunkt   : {dew:.2f} °C")

        influx_writer.log_metric(
            "dht22",
            {"temp": float(temp), "hum": float(hum), "dewpoint": float(dew)},
            tags={"host": "host1"}
        )

        if getattr(config, "DHT22_OVERLAY", False):
            overlay_dir = os.path.join(config.ALLSKY_PATH, "config", "overlay", "extra")
            os.makedirs(overlay_dir, exist_ok=True)
            overlay_path = os.path.join(overlay_dir, "dht22_overlay.json")
            overlay_data = {
                "DHT22_TEMP": {"value": f"{temp:.1f}", "format": "{:.1f}"},
                "DHT22_HUM" : {"value": f"{hum:.1f}",  "format": "{:.1f}"},
            }
            with open(overlay_path, "w") as f:
                json.dump(overlay_data, f, indent=2)

    except Exception as e:
        error(f" Fehler beim Auslesen/Schreiben der DHT22-Daten: {e}")

if __name__ == "__main__":
    main()
