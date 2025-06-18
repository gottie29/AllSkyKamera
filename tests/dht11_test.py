#!/usr/bin/env python3
import time
import pigpio

GPIO_PIN = 4  # GPIO 4 (physisch Pin 7)

def read_dht11(pi, gpio):
    h, t = pi.read_dht11(gpio)
    return h, t

def main():
    print("📡 DHT11 Standalone-Test über GPIO 4")
    pi = pigpio.pi()

    if not pi.connected:
        print("❌ pigpiod nicht gestartet. Bitte mit `sudo systemctl start pigpiod` starten.")
        return

    try:
        humidity, temperature = read_dht11(pi, GPIO_PIN)
        if humidity is not None and temperature is not None:
            print(f"🌡️ Temperatur: {temperature:.1f} °C")
            print(f"💧 Luftfeuchte: {humidity:.1f} %")
        else:
            print("❌ Keine gültigen Messwerte erhalten. Bitte Verkabelung prüfen.")
    finally:
        pi.stop()

if __name__ == "__main__":
    main()
