import Adafruit_DHT
from askutils import config

def is_connected():
    try:
        humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT11, config.DHT11_GPIO)
        return humidity is not None and temperature is not None
    except Exception:
        return False

def read_dht11():
    humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT11, config.DHT11_GPIO)
    if humidity is None or temperature is None:
        raise RuntimeError("Keine gültigen DHT11-Werte erhalten.")
    return {
        "temperature": round(temperature, 2),
        "humidity": round(humidity, 2)
    }
