#!/usr/bin/env python3
"""
TSL2591 light sensor test script

- Interface: I2C (busio + Adafruit Blinka)
- Reads lux, visible, IR, full spectrum
- Computes sky brightness (mag/arcsec^2)
- ASCII-only, English-only
"""

import math
import time
import sys

# Try imports
try:
    import board
    import busio
except ImportError:
    print("ERROR: Could not import 'board' or 'busio'.")
    print("Install Adafruit Blinka:")
    print("  sudo pip3 install adafruit-blinka")
    sys.exit(1)

try:
    import adafruit_tsl2591
except ImportError:
    print("ERROR: Module 'adafruit_tsl2591' not installed.")
    print("Install with:")
    print("  sudo pip3 install adafruit-circuitpython-tsl2591")
    sys.exit(1)


def safe_value(x, fallback=0.0001):
    if x is None or x <= 0:
        return fallback
    return float(x)


def compute_sky_brightness(lux):
    # mag/arcsec^2 = 22 - 2.5 * log10(lux)
    return 22.0 - 2.5 * math.log10(lux)


def main():
    print("=== TSL2591 Light Sensor Test ===")
    print("Interface: I2C (SCL/SDA)")
    print("This test reads a few samples and then exits.\n")

    try:
        i2c = busio.I2C(board.SCL, board.SDA)
    except Exception as e:
        print("ERROR: Could not open I2C interface.")
        print("Hint: enable I2C using 'sudo raspi-config'.")
        print("Exception:", e)
        sys.exit(1)

    try:
        sensor = adafruit_tsl2591.TSL2591(i2c)
    except Exception as e:
        print("ERROR: Could not initialize TSL2591 sensor.")
        print("Check wiring and address (default 0x29).")
        print("Exception:", e)
        sys.exit(1)

    samples = 5

    for i in range(samples):
        try:
            lux = safe_value(sensor.lux)
            visible = safe_value(sensor.visible)
            infrared = safe_value(sensor.infrared)
            full = safe_value(sensor.full_spectrum)
        except Exception as e:
            print("ERROR: Failed to read data from TSL2591:", e)
            break

        # Compute sky brightness
        skybright = compute_sky_brightness(lux)
        skybright2 = compute_sky_brightness(visible)

        # Optional threshold as in your original script
        if skybright2 < 6.0:
            skybright2 = 0.0001

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        print(f"[{timestamp}] Lux: {lux:.3f} lx")
        print(f"  Visible     : {visible:.3f}")
        print(f"  Infrared    : {infrared:.3f}")
        print(f"  Full spec   : {full:.3f}")
        print(f"  SkyBright   : {skybright:.2f} mag/arcsec^2")
        print(f"  SkyBrightVis: {skybright2:.2f} mag/arcsec^2")
        print()

        time.sleep(2.0)

    print("TSL2591 test finished.")


if __name__ == "__main__":
    main()
