# askutils/sensors/dhtxx.py
import time
import math
import statistics
import board
import adafruit_dht

from .. import config

# ---- Hilfen ----
def _board_pin_from_bcm(bcm_or_label):
    """
    Erwartet entweder eine int (BCM-Nummer, z.B. 6) oder
    einen String wie 'D6'/'GPIO6'. Gibt das passende board-Objekt zurück.
    """
    if isinstance(bcm_or_label, int):
        attr = f"D{bcm_or_label}"
        return getattr(board, attr)
    if isinstance(bcm_or_label, str):
        s = bcm_or_label.strip().upper()
        if s.startswith("GPIO"):
            s = "D" + s[4:]
        return getattr(board, s)
    raise ValueError("Ungültiger GPIO-Wert in config")

def _valid_temp_range(sensor_type):
    # konservativ: DHT11 oft 0..50°C, DHT22 -40..80°C
    return (-20.0, 60.0) if sensor_type == "DHT11" else (-40.0, 85.0)

def _read_median(dht, retries, delay, t_min, t_max):
    temps, hums = [], []
    for _ in range(max(1, int(retries))):
        try:
            t = dht.temperature
            h = dht.humidity
            if t is not None and h is not None and t_min <= float(t) <= t_max and 0.0 <= float(h) <= 100.0:
                temps.append(float(t))
                hums.append(float(h))
        except RuntimeError:
            # typisches, harmloses Read-Error-Verhalten der DHT-Lib
            pass
        time.sleep(delay)
    if temps and hums:
        return statistics.median(temps), statistics.median(hums)
    return None, None

def calculate_dew_point(temp_c, rel_hum):
    """Magnus-Formel (wie bei BME280 genutzt)"""
    a = 17.62
    b = 243.12
    alpha = ((a * temp_c) / (b + temp_c)) + math.log(rel_hum / 100.0)
    return round((b * alpha) / (a - alpha), 2)

# ---- Public API: DHT11 ----
def read_dht11():
    if not getattr(config, "DHT11_ENABLED", False):
        raise RuntimeError("DHT11 ist in config.py deaktiviert!")

    pin = _board_pin_from_bcm(getattr(config, "DHT11_GPIO_BCM", 6))
    retries = getattr(config, "DHT11_RETRIES", 10)
    delay   = getattr(config, "DHT11_RETRY_DELAY", 0.3)

    dht = adafruit_dht.DHT11(pin, use_pulseio=False)
    time.sleep(2.0)  # Sensor stabilisieren
    t_min, t_max = _valid_temp_range("DHT11")
    t, h = _read_median(dht, retries, delay, t_min, t_max)
    if t is None:
        raise RuntimeError("Keine gültigen DHT11-Werte erhalten")
    return round(t, 2), round(h, 2)

# ---- Public API: DHT22 ----
def read_dht22():
    if not getattr(config, "DHT22_ENABLED", False):
        raise RuntimeError("DHT22 ist in config.py deaktiviert!")

    pin = _board_pin_from_bcm(getattr(config, "DHT22_GPIO_BCM", 6))
    retries = getattr(config, "DHT22_RETRIES", 10)
    delay   = getattr(config, "DHT22_RETRY_DELAY", 0.3)

    dht = adafruit_dht.DHT22(pin, use_pulseio=False)
    time.sleep(2.0)
    t_min, t_max = _valid_temp_range("DHT22")
    t, h = _read_median(dht, retries, delay, t_min, t_max)
    if t is None:
        raise RuntimeError("Keine gültigen DHT22-Werte erhalten")
    return round(t, 2), round(h, 2)
