#!/usr/bin/env python3
import os
os.environ['ADAFRUIT_DHT_PLATFORM'] = 'Raspberry_Pi'

import Adafruit_DHT

sensor = Adafruit_DHT.DHT11
pin = 4  # GPIO 4 (Pin 7)

humidity, temperature = Adafruit_DHT.read_retry(sensor, pin)

if humidity is not None and temperature is not None:
    print(f"🌡️ Temperatur: {temperature:.1f} °C")
    print(f"💧 Feuchte:    {humidity:.1f} %")
else:
    print("❌ Fehler beim Auslesen des DHT11-Sensors.")
