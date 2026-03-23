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


def _slugify(name: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in name).strip("_")


def main():
    if not getattr(config, "DHT22_ENABLED", False):
        print("DHT22 ist deaktiviert. Messung uebersprungen.")
        return

    sensors = dhtxx.get_dht22_sensors()

    if not sensors:
        warn("Keine DHT22-Sensoren konfiguriert")
        return

    env_dir = os.path.join(os.path.dirname(__file__), "..", "tmp", "env")
    os.makedirs(env_dir, exist_ok=True)

    overlay_dir = os.path.join(config.ALLSKY_PATH, "config", "overlay", "extra")
    os.makedirs(overlay_dir, exist_ok=True)

    overlay_data = {}

    for idx, sensor in enumerate(sensors, start=1):
        try:
            if not sensor.get("enabled", True):
                continue

            name = sensor.get("name", f"DHT22_{idx}")
            slug = _slugify(name)

            temp, hum = dhtxx.read_dht22_sensor(sensor)
            dew = dhtxx.calculate_dew_point(temp, hum)

            print(f"[{name}]")
            print(f"  Temperatur : {temp:.2f} Grad_C")
            print(f"  Feuchte    : {hum:.2f} %")
            print(f"  Taupunkt   : {dew:.2f} Grad_C")

            # ---------------------------
            # Influx
            # ---------------------------
            try:
                influx_writer.log_metric(
                    "dht22",
                    {
                        "temp": float(temp),
                        "hum": float(hum),
                        "dewpoint": float(dew)
                    },
                    tags={
                        "host": "host1",
                        "sensor": name,
                        "gpio": str(sensor.get("gpio_bcm"))
                    }
                )
            except Exception as e:
                warn(f"Influx Fehler bei {name}: {e}")

            # ---------------------------
            # JSON pro Sensor
            # ---------------------------
            try:
                env_path = os.path.join(env_dir, f"dht22_{slug}.json")

                env_data = {
                    "ts": _iso_now_utc(),
                    "name": name,
                    "temp_c": float(temp),
                    "rh": float(hum),
                    "dewpoint_c": float(dew),
                }

                _atomic_write_json(env_path, env_data)

            except Exception as e:
                warn(f"Konnte JSON fuer {name} nicht schreiben: {e}")

            # ---------------------------
            # Overlay sammeln
            # ---------------------------
            if sensor.get("overlay", False):
                key_prefix = slug.upper()

                overlay_data[f"{key_prefix}_TEMP"] = {
                    "value": f"{temp:.1f}",
                    "format": "{:.1f}"
                }
                overlay_data[f"{key_prefix}_HUM"] = {
                    "value": f"{hum:.1f}",
                    "format": "{:.1f}"
                }

        except Exception as e:
            error(f"Fehler bei Sensor '{sensor.get('name')}': {e}")

    # ---------------------------
    # Overlay schreiben (alle Sensoren zusammen)
    # ---------------------------
    if overlay_data:
        try:
            overlay_path = os.path.join(overlay_dir, "dht22_overlay.json")
            with open(overlay_path, "w") as f:
                json.dump(overlay_data, f, indent=2)
        except Exception as e:
            warn(f"Konnte Overlay nicht schreiben: {e}")


if __name__ == "__main__":
    main()