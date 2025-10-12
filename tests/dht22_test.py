#!/usr/bin/env python3
import time
import statistics
import board
import adafruit_dht

# DHT22 (AM2302) an GPIO6 (Pin 31)
GPIO = board.D6

# Wichtiger Hinweis:
# Wenn du VCC auf 5V legst, muss der Pull-Up des DATA-Signals nach 3V3 gehen.

# Sensor initialisieren und kurze Wartezeit
dht = adafruit_dht.DHT22(GPIO, use_pulseio=False)
time.sleep(2.0)

def read_dht22(retries=10, delay=0.3):
    temps, hums = [], []
    for _ in range(retries):
        try:
            t = dht.temperature
            h = dht.humidity
            if t is not None and h is not None and -40.0 <= t <= 80.0 and 0.0 <= h <= 100.0:
                temps.append(float(t))
                hums.append(float(h))
        except RuntimeError:
            # typische DHT-Lesefehler ignorieren und erneut versuchen
            pass
        time.sleep(delay)
    if temps and hums:
        return statistics.median(temps), statistics.median(hums)
    return None, None

print("DHT22 Test auf GPIO6")
MEASURE_INTERVAL = 3.0  # nicht schneller als ca. alle 2 Sekunden

while True:
    t, h = read_dht22()
    if t is not None:
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  Temperatur: {t:.1f} C  Luftfeuchte: {h:.1f} %")
    else:
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  Keine gueltigen Werte")
    time.sleep(MEASURE_INTERVAL)
