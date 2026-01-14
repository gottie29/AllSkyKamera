#!/usr/bin/python3
import sys
import os
import json
import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from askutils import config
from askutils.sensors import ds18b20
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
    if not config.DS18B20_ENABLED:
        print("DS18B20 ist deaktiviert. Test wird uebersprungen.")
        return

    try:
        temp = ds18b20.read_ds18b20()
    except Exception as e:
        error(f"Fehler beim Auslesen des DS18B20: {e}")
        return

    print(f"Standort: {config.STANDORT_NAME} ({config.KAMERA_ID})")
    print(f"Temperatur: {temp:.2f} Grad_C")

    if float(temp) < -35.0 or float(temp) > 75.0:
        warn(f"Ungueltiger Temperaturwert: {temp:.2f} Grad_C")
        return

    influx_writer.log_metric("ds18b20", {
        "temp": float(temp)
    }, tags={"host": "host1"})

    # ---------------------------
    # NEU: Sensor-JSON in tmp/env/
    # ---------------------------
    try:
        env_dir = os.path.join(os.path.dirname(__file__), "..", "tmp", "env")
        os.makedirs(env_dir, exist_ok=True)
        env_path = os.path.join(env_dir, "ds18b20.json")

        env_data = {
            "ts": _iso_now_utc(),
            "temp_c": float(temp),
        }

        _atomic_write_json(env_path, env_data)
    except Exception as e:
        # Sensorlogging soll nicht komplett scheitern, nur weil JSON nicht geschrieben werden kann
        warn(f"Konnte ds18b20.json nicht schreiben: {e}")

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
