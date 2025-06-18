import Adafruit_DHT
humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT11, 11)  # GPIO 4
print(f"Temp: {temperature}, Hum: {humidity}")
