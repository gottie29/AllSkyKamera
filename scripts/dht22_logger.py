#!/usr/bin/env python3
import sys
import os
import json
import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from askutils import config
from askutils.sensors import dhtxx
from askutils.utils.logger import log, warn, error
from askutils.utils import influx_writer


def _iso_now_utc() -> str:
    import datetime
    return (
        datetime.datetime
        .now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _atomic_write_json(path: str, data: dict):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def main():
    if not getattr(config, "DHT22_ENABLED", False):
        print("DHT22 ist deaktiviert. Messung uebersprungen.")
        return

    try:
        temp, hum = dhtxx.read_dht22()
        dew = dhtxx.calculate_dew_point(temp, hum)

        print(f"Standort: {config.STANDORT_NAME} ({config.KAMERA_ID})")
        print(f"Temperatur : {temp:.2f} Grad_C")
        print(f"Feuchte    : {hum:.2f} %")
        print(f"Taupunkt   : {dew:.2f} Grad_C")

        influx_writer.log_metric(
            "dht22",
            {
                "temp": float(temp),
                "hum": float(hum),
                "dewpoint": float(dew)
            },
            tags={"host": "host1"}
        )

        # ---------------------------
        # NEU: Sensor-JSON in tmp/env/
        # ---------------------------
        try:
            env_dir = os.path.join(os.path.dirname(__file__), "..", "tmp", "env")
            os.makedirs(env_dir, exist_ok=True)
            env_path = os.path.join(env_dir, "dht22.json")

            env_data = {
                "ts": _iso_now_utc(),
                "temp_c": float(temp),
                "rh": float(hum),
                "dewpoint_c": float(dew),
            }

            _atomic_write_json(env_path, env_data)
        except Exception as e:
            warn(f"Konnte dht22.json nicht schreiben: {e}")

        if getattr(config, "DHT22_OVERLAY", False):
            overlay_dir = os.path.join(config.ALLSKY_PATH, "config", "overlay", "extra")
            os.makedirs(overlay_dir, exist_ok=True)
            overlay_path = os.path.join(overlay_dir, "dht22_overlay.json")
            overlay_data = {
                "DHT22_TEMP": {"value": f"{temp:.1f}", "format": "{:.1f}"},
                "DHT22_HUM":  {"value": f"{hum:.1f}",  "format": "{:.1f}"},
            }
            with open(overlay_path, "w") as f:
                json.dump(overlay_data, f, indent=2)

    except Exception as e:
        error(f" Fehler beim Auslesen/Schreiben der DHT22-Daten: {e}")


if __name__ == "__main__":
    main()
