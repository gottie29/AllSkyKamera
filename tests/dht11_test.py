#!/usr/bin/env python3
import sys, time, subprocess


# libgpiod wird als Debian-Paket geliefert; wir geben nur den Hinweis, falls es fehlt
try:
    import gpiod  # wird indirekt genutzt
except Exception:
    print("ℹ️ Hinweis: Falls gleich ein libgpiod-Fehler kommt, installiere erst: "
          "sudo apt install -y python3-libgpiod")

import board
import adafruit_dht

# --- Sensor konfigurieren ---
# Deine Verkabelung: DATA -> GPIO4 (Pin 7), VCC -> 3V3, GND -> GND
dht = adafruit_dht.DHT11(board.D6, use_pulseio=False)

print("=== DHT11 Temperatursensor Test (CircuitPython) ===")
while True:
    try:
        temp = dht.temperature          # °C
        hum  = dht.humidity             # %
        if temp is not None and hum is not None:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                  f"Temperatur: {temp:.1f} °C | Luftfeuchte: {hum:.1f} %")
        else:
            print("⚠️ Keine gültigen Messwerte (None) – lese erneut …")
    except RuntimeError as e:
        # DHTs liefern regelmäßig Lese-Fehler. Kurz warten und weiter.
        print(f"⚠️ Lesefehler: {e}")
    except Exception as e:
        print(f"❌ Unerwarteter Fehler: {e}")
        raise
    time.sleep(2)
