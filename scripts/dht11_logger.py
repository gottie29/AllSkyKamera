#!/usr/bin/python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from askutils import config
from askutils.utils.logger import log, warn, error
from askutils.utils import influx_writer
from askutils.sensors import dht11

def main():
    if not getattr(config, "DHT11_ENABLED", False):
        print("ℹ️ DHT11 ist deaktiviert. Messung übersprungen.")
        return

    if not dht11.is_connected():
        error("❌ DHT11 liefert keine Werte.")
        return

    try:
        data = dht11.read_dht11()
    except Exception as e:
        error(f"❌ Fehler beim Auslesen des DHT11: {e}")
        return

    print(f"📍 Standort: {config.STANDORT_NAME} ({config.KAMERA_ID})")
    print(f"🌡️ Temperatur : {data['temperature']} °C")
    print(f"💧 Feuchte    : {data['humidity']} %")

    #influx_writer.log_metric("dht11", {
    #    "temp": data["temperature"],
    #    "hum": data["humidity"]
    #}, tags={"host": "host1"})

if __name__ == "__main__":
    main()
