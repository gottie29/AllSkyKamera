#!/usr/bin/python3
import sys
import os
import json
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from askutils import config
from askutils.sensors.htu21 import HTU21, calculate_dew_point
from askutils.utils.logger import log, warn, error
from askutils.utils import influx_writer


def main():
    if not config.HTU21_ENABLED:
        print("HTU21 ist deaktiviert. Test wird uebersprungen.")
        return

    try:
        sensor = HTU21()
    except Exception as e:
        error(f"Sensor nicht erreichbar: {e}")
        return

    try:
        temp, hum = sensor.read()
        taupunkt = calculate_dew_point(temp, hum)

        print(f"Standort: {config.STANDORT_NAME} ({config.KAMERA_ID})")
        print(f"Temperatur : {temp:.2f} Grad_C")
        print(f"Feuchte    : {hum:.2f} %")
        print(f"Taupunkt   : {taupunkt:.2f} Grad_C")

        # InfluxDB
        influx_writer.log_metric("htu21", {
            "temp": float(temp),
            "hum": float(hum),
            "dewpoint": float(taupunkt),
        }, tags={"host": "host1"})

        if config.HTU21_OVERLAY:
            overlay_dir = os.path.join(config.ALLSKY_PATH, "config", "overlay", "extra")
            os.makedirs(overlay_dir, exist_ok=True)

            overlay_path = os.path.join(overlay_dir, "htu21_overlay.json")
            overlay_data = {
                "HTU21_TEMP": {
                    "value": f"{temp:.1f}",
                    "format": "{:.1f}"
                },
                "HTU21_HUM": {
                    "value": f"{hum:.1f}",
                    "format": "{:.1f}"
                }
            }

            with open(overlay_path, "w") as f:
                json.dump(overlay_data, f, indent=2)

    except Exception as e:
        error(f"Fehler beim Auslesen oder Schreiben der HTU21-Daten: {e}")


if __name__ == "__main__":
    main()
