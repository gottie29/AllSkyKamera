#!/usr/bin/python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from askutils import config
from askutils.sensors import bme280
from askutils.utils.logger import log, warn, error
from askutils.utils import influx_writer

def main():
    if not config.BME280_ENABLED:
        print("ℹ️ BME280 ist deaktiviert. Test wird übersprungen.")
        return

    try:
        chip_id, chip_version = bme280.get_chip_id()
        if chip_id not in [0x60, 0x58]:  # 0x60 = BME280, 0x58 = BMP280
            warn(f"⚠️ Kein gültiger BME280 erkannt (Chip-ID: {hex(chip_id)}). Messung übersprungen.")
            return
    except Exception as e:
        error(f"❌ Sensor nicht erreichbar: {e}")
        return

    try:
        temp, pressure, hum = bme280.read_bme280()
        taupunkt = bme280.calculate_dew_point(temp, hum)

        print(f"📍 Standort: {config.STANDORT_NAME} ({config.KAMERA_ID})")
        print(f"🌡️ Temperatur : {temp:.2f} °C")
        print(f"🧭 Druck      : {pressure:.2f} hPa")
        print(f"💧 Feuchte    : {hum:.2f} %")
        print(f"❄️ Taupunkt   : {taupunkt:.2f} °C")

        influx_writer.log_metric("bme280", {
            "temp": float(temp),
            "press": float(pressure),
            "hum": float(hum),
            "dewpoint": float(taupunkt),
        }, tags={"host": "host1"})

    except Exception as e:
        error(f"❌ Fehler beim Auslesen oder Schreiben der BME280-Daten: {e}")

if __name__ == "__main__":
    main()
