#!/usr/bin/python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from askutils import config
from askutils.sensors import bme280
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

def main():
    if not config.BME280_ENABLED:
        print("ℹ️ BME280 ist deaktiviert. Test wird übersprungen.")
        return

    chip_id, chip_version = bme280.get_chip_id()
    temp, pressure, hum = bme280.read_bme280()
    taupunkt = bme280.calculate_dew_point(temp, hum)

    print(f"📍 Standort: {config.STANDORT_NAME} ({config.KAMERA_ID})")
    print(f"🌡️ Temperatur : {temp:.2f} °C")
    print(f"🧭 Druck      : {pressure:.2f} hPa")
    print(f"💧 Feuchte    : {hum:.2f} %")
    print(f"❄️ Taupunkt   : {taupunkt:.2f} °C")

if __name__ == "__main__":
    main()
