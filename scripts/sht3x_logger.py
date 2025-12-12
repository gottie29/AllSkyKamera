#!/usr/bin/python3
import sys
import os
import json

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from askutils import config
from askutils.sensors.sht3x import SHT3x, calculate_dew_point
from askutils.utils.logger import log, warn, error
from askutils.utils import influx_writer


def main():
    if not getattr(config, "SHT3X_ENABLED", False):
        print("SHT3x is disabled. Skipping measurement.")
        return

    try:
        sensor = SHT3x()
    except Exception as e:
        error(f"SHT3x sensor not reachable: {e}")
        return

    try:
        temp, hum = sensor.read()
        dewpoint = calculate_dew_point(temp, hum)

        print(f"Location   : {config.STANDORT_NAME} ({config.KAMERA_ID})")
        print(f"Temperature: {temp:.2f} C")
        print(f"Humidity   : {hum:.2f} %")
        print(f"Dew point  : {dewpoint:.2f} C")

        # InfluxDB
        influx_writer.log_metric(
            "sht3x",
            {
                "temp": float(temp),
                "hum": float(hum),
                "dewpoint": float(dewpoint),
            },
            tags={"host": "host1"},
        )

        # Optional overlay file for AllSky overlays
        if getattr(config, "SHT3X_OVERLAY", False):
            overlay_dir = os.path.join(
                config.ALLSKY_PATH, "config", "overlay", "extra"
            )
            os.makedirs(overlay_dir, exist_ok=True)

            overlay_path = os.path.join(overlay_dir, "sht3x_overlay.json")
            overlay_data = {
                "SHT3X_TEMP": {
                    "value": f"{temp:.1f}",
                    "format": "{:.1f}",
                },
                "SHT3X_HUM": {
                    "value": f"{hum:.1f}",
                    "format": "{:.1f}",
                },
            }

            with open(overlay_path, "w") as f:
                json.dump(overlay_data, f, indent=2)

    except Exception as e:
        error(f"Error while reading or writing SHT3x data: {e}")


if __name__ == "__main__":
    main()
