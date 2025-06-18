import time
import board
import adafruit_dht

# Sensor initialisieren (GPIO 4)
dhtDevice = adafruit_dht.DHT11(board.D4)

print("📡 DHT11-Test über GPIO 4")

try:
    temperature = dhtDevice.temperature
    humidity = dhtDevice.humidity

    if humidity is not None and temperature is not None:
        print(f"🌡️ Temperatur: {temperature:.1f} °C")
        print(f"💧 Feuchte:    {humidity:.1f} %")
    else:
        print("❌ Keine gültigen Messwerte erhalten.")
except Exception as e:
    print(f"⚠️ Fehler beim Auslesen: {e}")
finally:
    dhtDevice.exit()
