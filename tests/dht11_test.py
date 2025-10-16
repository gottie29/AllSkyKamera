#!/usr/bin/env python3
import time
import statistics
import board
import adafruit_dht

# DHT11 an GPIO6 (Pin 31), VCC 3.3V, GND
GPIO = board.D6
dht = adafruit_dht.DHT11(GPIO, use_pulseio=False)
time.sleep(2.0)

SAMPLE_INTERVAL = 10
SAMPLES_PER_BLOCK = 5

def read_dht11(retries=10, delay=0.3):
    """Mehrfaches Lesen und Medianbildung pro Einzelmessung."""
    temps, hums = [], []
    for _ in range(retries):
        try:
            t = dht.temperature
            h = dht.humidity
            if t is not None and h is not None and -20.0 <= t <= 60.0 and 0.0 <= h <= 100.0:
                temps.append(float(t))
                hums.append(float(h))
        except RuntimeError:
            pass
        time.sleep(delay)
    if temps and hums:
        return statistics.median(temps), statistics.median(hums)
    return None, None

print("DHT11 average measurement ("+str(SAMPLES_PER_BLOCK)+" values every "+str(SAMPLE_INTERVAL)+" seconds)")

temp_values = []
hum_values = []

while True:
    t, h = read_dht11()
    if t is not None:
        temp_values.append(t)
        hum_values.append(h)
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  Single: {t:.1f} C  {h:.1f} %  ({len(temp_values)}/{SAMPLES_PER_BLOCK})")
    else:
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  No valid values")

    if len(temp_values) >= SAMPLES_PER_BLOCK:
        avg_temp = statistics.mean(temp_values)
        avg_hum = statistics.mean(hum_values)
        print("-----------------------------------------------")
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  Average of {SAMPLES_PER_BLOCK} samples")
        print(f"Temperature: {avg_temp:.2f} C  Humidity: {avg_hum:.2f} %")
        print("-----------------------------------------------")
        temp_values.clear()
        hum_values.clear()

    time.sleep(SAMPLE_INTERVAL)
