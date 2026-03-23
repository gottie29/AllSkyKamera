#!/usr/bin/python3
import sys
import os
import json
import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from askutils import config
from askutils.sensors import bme280
from askutils.utils.logger import warn, error
from askutils.utils import influx_writer


def _iso_now_utc():
    return (
        datetime.datetime
        .now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _atomic_write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def _safe_name(name):
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in str(name))


def main():
    sensors = bme280.get_enabled_sensors()
    if not sensors:
        print("BME280 ist deaktiviert. Test wird uebersprungen.")
        return

    env_dir = os.path.join(os.path.dirname(__file__), "..", "tmp", "env")
    os.makedirs(env_dir, exist_ok=True)

    overlay_dir = os.path.join(config.ALLSKY_PATH, "config", "overlay", "extra")
    os.makedirs(overlay_dir, exist_ok=True)

    all_results = []

    for sensor in sensors:
        sensor_name = sensor.get("name", "BME280")
        sensor_addr = int(sensor.get("address", 0x76))

        try:
            chip = bme280.get_chip_id(sensor_addr)
            chip_id = chip[0]
            chip_version = chip[1]

            if chip_id not in [0x60, 0x58]:
                warn(
                    "Kein gueltiger BME280/BMP280 erkannt fuer Sensor '{}' "
                    "(Adresse {}, Chip-ID: {}).".format(
                        sensor_name, hex(sensor_addr), hex(chip_id)
                    )
                )
                continue

            temp, pressure, hum = bme280.read_sensor(sensor)
            taupunkt = bme280.calculate_dew_point(temp, hum)

            print("Standort: {} ({})".format(config.STANDORT_NAME, config.KAMERA_ID))
            print("Sensor      : {} ({})".format(sensor_name, hex(sensor_addr)))
            print("Temperatur  : {:.2f} Grad_C".format(temp))
            print("Druck       : {:.2f} hPa".format(pressure))
            print("Feuchte     : {:.2f} %".format(hum))
            if taupunkt is not None:
                print("Taupunkt    : {:.2f} Grad_C".format(taupunkt))
            print("")

            influx_writer.log_metric(
                "bme280",
                {
                    "temp": float(temp),
                    "press": float(pressure),
                    "hum": float(hum),
                    "dewpoint": float(taupunkt) if taupunkt is not None else 0.0,
                },
                tags={
                    "host": "host1",
                    "sensor": sensor_name,
                    "address": hex(sensor_addr),
                }
            )

            env_data = {
                "ts": _iso_now_utc(),
                "name": sensor_name,
                "address": hex(sensor_addr),
                "temp_c": float(temp),
                "rh": float(hum),
                "pressure_hpa": float(pressure),
                "dewpoint_c": float(taupunkt) if taupunkt is not None else None,
            }

            sensor_filename = "bme280_{}.json".format(_safe_name(sensor_name))
            sensor_path = os.path.join(env_dir, sensor_filename)
            _atomic_write_json(sensor_path, env_data)

            all_results.append(env_data)

            if sensor.get("overlay", False):
                overlay_path = os.path.join(overlay_dir, "bme280_overlay.json")
                overlay_data = {
                    "BME280_TEMP": {
                        "value": "{:.1f}".format(temp),
                        "format": "{:.1f}"
                    },
                    "BME280_PRESS": {
                        "value": "{:.2f}".format(pressure),
                        "format": "{:.2f}"
                    },
                    "BME280_HUM": {
                        "value": "{:.1f}".format(hum),
                        "format": "{:.1f}"
                    }
                }
                with open(overlay_path, "w") as f:
                    json.dump(overlay_data, f, indent=2)

        except Exception as e:
            error(
                "Fehler bei Sensor '{}' an Adresse {}: {}".format(
                    sensor_name, hex(sensor_addr), e
                )
            )

    # Sammeldatei schreiben
    if all_results:
        combined_path = os.path.join(env_dir, "bme280.json")
        _atomic_write_json(combined_path, {
            "ts": _iso_now_utc(),
            "sensors": all_results
        })


if __name__ == "__main__":
    main()