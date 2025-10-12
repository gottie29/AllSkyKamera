import board
import busio
import adafruit_tsl2591

import math

def main():
    # Sensor initialisieren
    i2c = busio.I2C(board.SCL, board.SDA)
    sensor = adafruit_tsl2591.TSL2591(i2c)

    # Daten holen
    lux = sensor.lux or 0.0001
    visible = sensor.visible or 0.0001
    infrared = sensor.infrared or 0.0001
    full = sensor.full_spectrum or 0.0001

    skybright = 22.0 - 2.5 * math.log10(lux)
    skybright2 = 22.0 - 2.5 * math.log10(visible)
    if (skybright2 < 6.0):
        skybright2 = 0.0001



    print(f"Lux-Wert      : {lux:.2f} lx")
    print(f"Sichtbar      : {visible}")
    print(f"Infrarot      : {infrared}")
    print(f"Vollspektrum  : {full}")
    print(f"Himmelshelligkeit (mag/arcsec²): {skybright:.2f}")
    print(f"Himmelshelligkeit Vis (mag/arcsec²): {skybright2:.2f}")

if __name__ == "__main__":
    main()

