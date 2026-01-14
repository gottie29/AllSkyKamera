#!/usr/bin/python3
import sys
import os
import json
import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from askutils import config
from askutils.sensors import bme280
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
    if not config.BME280_ENABLED:
        print("BME280 ist deaktiviert. Test wird uebersprungen.")
        return

    try:
        chip_id, chip_version = bme280.get_chip_id()
        if chip_id not in [0x60, 0x58]:  # 0x60 = BME280, 0x58 = BMP280
            warn(f"Kein gueltiger BME280 erkannt (Chip-ID: {hex(chip_id)}). Messung uebersprungen.")
            return
    except Exception as e:
        error(f" Sensor nicht erreichbar: {e}")
        return

    try:
        temp, pressure, hum = bme280.read_bme280()
        taupunkt = bme280.calculate_dew_point(temp, hum)

        print(f"Standort: {config.STANDORT_NAME} ({config.KAMERA_ID})")
        print(f"Temperatur : {temp:.2f} Grad_C")
        print(f" Druck      : {pressure:.2f} hPa")
        print(f"Feuchte    : {hum:.2f} %")
        print(f"Taupunkt   : {taupunkt:.2f} Grad_C")

        influx_writer.log_metric("bme280", {
            "temp": float(temp),
            "press": float(pressure),
            "hum": float(hum),
            "dewpoint": float(taupunkt),
        }, tags={"host": "host1"})

        # ---------------------------
        # NEU: Sensor-JSON in tmp/env/
        # ---------------------------
        env_dir = os.path.join(os.path.dirname(__file__), "..", "tmp", "env")
        os.makedirs(env_dir, exist_ok=True)
        env_path = os.path.join(env_dir, "bme280.json")

        env_data = {
            "ts": _iso_now_utc(),
            "temp_c": float(temp),
            "rh": float(hum),
            "pressure_hpa": float(pressure),
            "dewpoint_c": float(taupunkt),
        }

        _atomic_write_json(env_path, env_data)

        # Overlay schreiben, wenn aktiviert
        if config.BME280_OVERLAY:
            overlay_dir = os.path.join(config.ALLSKY_PATH, "config", "overlay", "extra")
            os.makedirs(overlay_dir, exist_ok=True)
            overlay_path = os.path.join(overlay_dir, "bme280_overlay.json")
            overlay_data = {
                "BME280_TEMP": {
                    "value": f"{temp:.1f}",
                    "format": "{:.1f}"
                },
                "BME280_PRESS": {
                    "value": f"{pressure:.2f}",
                    "format": "{:.2f}"
                },
                "BME280_HUM": {
                    "value": f"{hum:.1f}",
                    "format": "{:.1f}"
                }
            }
            with open(overlay_path, "w") as f:
                json.dump(overlay_data, f, indent=2)

    except Exception as e:
        error(f" Fehler beim Auslesen oder Schreiben der BME280-Daten: {e}")


if __name__ == "__main__":
    main()
