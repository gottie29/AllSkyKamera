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
    einen String wie 'D6'/'GPIO6'. Gibt das passende board-Objekt zurueck.
    """
    if isinstance(bcm_or_label, int):
        attr = f"D{bcm_or_label}"
        return getattr(board, attr)
    if isinstance(bcm_or_label, str):
        s = bcm_or_label.strip().upper()
        if s.startswith("GPIO"):
            s = "D" + s[4:]
        return getattr(board, s)
    raise ValueError("Ungueltiger GPIO-Wert in config")

def _valid_temp_range(sensor_type):
    # konservativ: DHT11 oft 0..50Grad_C, DHT22 -40..80Grad_C
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

def _apply_calibration(sensor_prefix: str, t: float, h: float):
    """
    sensor_prefix: 'DHT11' oder 'DHT22'
    wendet Offset + optional Clamp an.
    """
    t_off = float(getattr(config, f"{sensor_prefix}_TEMP_OFFSET_C", 0.0) or 0.0)
    h_off = float(getattr(config, f"{sensor_prefix}_HUM_OFFSET_PCT", 0.0) or 0.0)
    t = float(t) + t_off
    h = float(h) + h_off

    # Clamp Defaults (falls nicht gesetzt)
    if hasattr(config, f"{sensor_prefix}_TEMP_MIN_C"):
        t_min = float(getattr(config, f"{sensor_prefix}_TEMP_MIN_C"))
    else:
        t_min = _valid_temp_range(sensor_prefix)[0]

    if hasattr(config, f"{sensor_prefix}_TEMP_MAX_C"):
        t_max = float(getattr(config, f"{sensor_prefix}_TEMP_MAX_C"))
    else:
        t_max = _valid_temp_range(sensor_prefix)[1]

    h_min = float(getattr(config, f"{sensor_prefix}_HUM_MIN_PCT", 0.0) or 0.0)
    h_max = float(getattr(config, f"{sensor_prefix}_HUM_MAX_PCT", 100.0) or 100.0)

    if t < t_min: t = t_min
    if t > t_max: t = t_max
    if h < h_min: h = h_min
    if h > h_max: h = h_max

    return t, h

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
    if t is None or h is None:
        raise RuntimeError("Keine gueltigen DHT11-Werte erhalten")

    t, h = _apply_calibration("DHT11", t, h)
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
    if t is None or h is None:
        raise RuntimeError("Keine gueltigen DHT22-Werte erhalten")

    t, h = _apply_calibration("DHT22", t, h)
    return round(t, 2), round(h, 2)
