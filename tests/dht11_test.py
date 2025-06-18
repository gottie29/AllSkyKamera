from gpiozero import DigitalInputDevice
import time

# Einfache manuelle Auslese (rudimentär)
def is_connected():
    try:
        sensor = DigitalInputDevice(4)  # GPIO 4
        return True
    except Exception:
        return False

def read_dht11():
    raise NotImplementedError("Nutze besser DHT11 über alternative Lib wie `pigpio` oder externen Dienst.")
