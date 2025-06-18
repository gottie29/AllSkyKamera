import time
import pigpio
from askutils import config

DHT11_GPIO = config.DHT11_GPIO

class DHT11Reader:
    def __init__(self, pi, gpio):
        self.pi = pi
        self.gpio = gpio
        self.humidity = None
        self.temperature = None

    def read(self):
        h, t = self.pi.read_dht11(self.gpio)
        if h is not None and t is not None:
            self.humidity = h
            self.temperature = t
            return True
        return False

def is_connected():
    try:
        pi = pigpio.pi()
        h, t = pi.read_dht11(DHT11_GPIO)
        pi.stop()
        return h is not None and t is not None
    except Exception:
        return False

def read_dht11():
    pi = pigpio.pi()
    try:
        h, t = pi.read_dht11(DHT11_GPIO)
        if h is None or t is None:
            raise RuntimeError("Keine gültigen DHT11-Werte.")
        return {
            "temperature": round(t, 2),
            "humidity": round(h, 2)
        }
    finally:
        pi.stop()
