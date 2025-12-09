#!/usr/bin/env python3
"""
DS18B20 Test Script (1-Wire bus)

- Uses a DS18B20 connected via the Raspberry Pi 1-Wire interface
- Reads temperature values from /sys/bus/w1/devices/
- Prints clear error messages if modules or sensors are missing
- ASCII-only, English-only
- Runs a limited number of measurements for testing
"""

import os
import glob
import time


BASE_DIR = "/sys/bus/w1/devices/"
MAX_READS = 10               # number of test samples
READ_INTERVAL = 2            # seconds between reads


def check_1wire_modules():
    """Check if required kernel modules are loaded."""
    modules = os.popen("lsmod").read()

    if "w1_gpio" not in modules or "w1_therm" not in modules:
        print("[ERROR] 1-Wire kernel modules are not loaded.")
        print("Please enable 1-Wire interface with:")
        print("  sudo raspi-config")
        print("Interface Options -> 1-Wire -> Enable")
        print()
        return False

    return True


def read_ds18b20():
    """Read temperature from first detected DS18B20 sensor."""
    device_folders = glob.glob(BASE_DIR + "28-*")

    if not device_folders:
        return None, "No DS18B20 sensor found on the 1-Wire bus"

    device_file = os.path.join(device_folders[0], "w1_slave")

    if not os.path.exists(device_file):
        return None, "Sensor file not found: " + device_file

    try:
        with open(device_file, "r") as f:
            lines = f.readlines()

        # Check CRC
        if not lines[0].strip().endswith("YES"):
            return None, "CRC check failed (bad read)"

        # Extract temperature value
        pos = lines[1].find("t=")
        if pos != -1:
            temp_string = lines[1][pos + 2 :]
            temperature_c = float(temp_string) / 1000.0
            return temperature_c, None

        return None, "Unexpected sensor output format"

    except Exception as e:
        return None, "Exception during read: {}".format(e)


def main():
    print("=== DS18B20 Test (1-Wire bus) ===")
    print("Interface: 1-Wire (w1_gpio)")
    print("Sensor path: {}".format(BASE_DIR))
    print("Reads: {} samples".format(MAX_READS))
    print()

    if not check_1wire_modules():
        return

    print("Starting DS18B20 test...")
    print()

    for i in range(MAX_READS):
        temp, err = read_ds18b20()
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        if err:
            print("{}  ERROR: {}".format(timestamp, err))
        else:
            print("{}  Temperature: {:.2f} C".format(timestamp, temp))

        time.sleep(READ_INTERVAL)

    print()
    print("DS18B20 test completed.")
    print("================================")


if __name__ == "__main__":
    main()
