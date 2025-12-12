#!/usr/bin/env python3
"""
SHT3x (SHT30 / SHT31 / SHT35) simple test script for Raspberry Pi

- Reads temperature (C) and humidity (%)
- Uses I2C bus 1 and default address 0x44
- Performs a single measurement using "High repeatability, clock stretching disabled" command
- Computes dew point
- Prints results and exits
"""

import sys
import time
import math
import datetime

# ---------------------------------------------------------
# Dependencies
# ---------------------------------------------------------
try:
    import smbus2
except ImportError:
    print("Error: smbus2 is not installed.")
    print("Install it using:")
    print("  sudo apt install python3-smbus")
    print("or:")
    print("  pip3 install smbus2")
    sys.exit(1)

# ---------------------------------------------------------
# Sensor configuration
# ---------------------------------------------------------
I2C_BUS = 1
I2C_ADDR = 0x44

# Single-shot measurement command (no clock stretching)
# Datasheet: 0x24, 0x00 = High repeatability, 15 ms typical measurement time
CMD_SINGLE_SHOT = [0x24, 0x00]


def calculate_dew_point(temp_c: float, humidity: float) -> float:
    """Calculate dew point using Magnus formula."""
    if humidity <= 0:
        return float("nan")
    a = 17.62
    b = 243.12
    alpha = ((a * temp_c) / (b + temp_c)) + math.log(humidity / 100.0)
    dew = (b * alpha) / (a - alpha)
    return round(dew, 2)


class SHT3x:
    """Simple SHT3x reader."""

    def __init__(self, bus: int = I2C_BUS, address: int = I2C_ADDR):
        self.bus_num = bus
        self.address = address

        try:
            self.bus = smbus2.SMBus(bus)
        except Exception as e:
            raise RuntimeError(f"Could not open I2C bus {bus}: {e}")

    def read(self):
        """Perform a single-shot measurement."""
        try:
            # Send single-shot command
            self.bus.write_i2c_block_data(self.address, CMD_SINGLE_SHOT[0], CMD_SINGLE_SHOT[1:])
        except Exception as e:
            raise RuntimeError(f"I2C write failed: {e}")

        time.sleep(0.020)  # wait for measurement

        try:
            data = self.bus.read_i2c_block_data(self.address, 0x00, 6)
        except Exception as e:
            raise RuntimeError(f"I2C read failed: {e}")

        if len(data) != 6:
            raise RuntimeError(f"Unexpected data length {len(data)}, expected 6 bytes.")

        raw_t = (data[0] << 8) | data[1]
        raw_h = (data[3] << 8) | data[4]

        # Temperature conversion
        temp_c = -45 + (175 * (raw_t / 65535.0))
        # Humidity conversion
        hum = 100 * (raw_h / 65535.0)

        return round(temp_c, 2), round(hum, 2)


def main():
    print("=== SHT3x Test (SHT30 / SHT31 / SHT35) ===")
    print(f"Using I2C bus {I2C_BUS} and address 0x{I2C_ADDR:02X}")
    print("Make sure the sensor is connected and I2C is enabled (sudo raspi-config).")
    print()

    try:
        sensor = SHT3x()
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        print("Hint: Run 'sudo i2cdetect -y 1' to check for device presence.")
        sys.exit(1)

    try:
        temp_c, hum = sensor.read()
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    dew = calculate_dew_point(temp_c, hum)
    timestamp = datetime.datetime.now().isoformat(timespec="seconds")

    print(f"Timestamp   : {timestamp}")
    print(f"Temperature : {temp_c:.2f} C")
    print(f"Humidity    : {hum:.2f} %")
    print(f"Dew point   : {dew:.2f} C")
    print()
    print("Test finished. Exiting.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted by user.")
        sys.exit(0)
    except Exception as exc:
        print(f"[UNEXPECTED ERROR] {exc}")
        sys.exit(1)
