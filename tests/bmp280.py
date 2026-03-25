#!/usr/bin/env python3
"""
Simple BMP280 test script.

- Uses I2C bus 1 and device address 0x76 by default.
- Prints one measurement (temperature, pressure, estimated altitude) and exits.
- Shows clear error messages if:
  * the smbus library is missing
  * the I2C bus or device cannot be reached
  * the detected chip is not a BMP280
"""

import sys
import time
import math
import datetime

try:
    import smbus
except ImportError:
    print("[ERROR] Python module 'smbus' is not installed.")
    print("        Install it with:")
    print("        sudo apt-get update")
    print("        sudo apt-get install python3-smbus i2c-tools")
    sys.exit(1)

from ctypes import c_short

DEVICE_ADDRESS = 0x76
BUS_NUMBER = 1

# Standard-Luftdruck auf MeereshÃ¶he in hPa
SEA_LEVEL_PRESSURE_HPA = 1013.25

try:
    bus = smbus.SMBus(BUS_NUMBER)
except FileNotFoundError:
    print(f"[ERROR] I2C bus {BUS_NUMBER} could not be opened.")
    print("        Make sure I2C is enabled (raspi-config) and the correct bus number is used.")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Could not initialize I2C bus {BUS_NUMBER}: {e}")
    sys.exit(1)


def get_short(data, index):
    return c_short((data[index + 1] << 8) + data[index]).value


def get_ushort(data, index):
    return (data[index + 1] << 8) + data[index]


def read_chip_id(addr=DEVICE_ADDRESS):
    REG_ID = 0xD0
    try:
        chip_id = bus.read_byte_data(addr, REG_ID)
        chip_version = bus.read_byte_data(addr, REG_ID + 1)
    except OSError as e:
        raise RuntimeError(
            f"I2C communication failed when reading chip ID at address 0x{addr:02X} on bus {BUS_NUMBER}. "
            "Check wiring, sensor power, and that I2C is enabled."
        ) from e
    return chip_id, chip_version


def read_bmp280_all(addr=DEVICE_ADDRESS):
    """
    Read temperature and pressure from BMP280.
    Returns:
        temperature_c, pressure_hpa
    """
    REG_DATA = 0xF7
    REG_CONTROL = 0xF4
    REG_CONFIG = 0xF5

    OVERSAMPLE_TEMP = 2
    OVERSAMPLE_PRES = 2
    MODE = 1  # forced mode
    STANDBY = 0
    FILTER = 0
    SPI3W_EN = 0

    try:
        # Configuration register
        config = (STANDBY << 5) | (FILTER << 2) | SPI3W_EN
        bus.write_byte_data(addr, REG_CONFIG, config)

        # Control register
        control = (OVERSAMPLE_TEMP << 5) | (OVERSAMPLE_PRES << 2) | MODE
        bus.write_byte_data(addr, REG_CONTROL, control)

        # Read calibration data
        cal = bus.read_i2c_block_data(addr, 0x88, 24)
    except OSError as e:
        raise RuntimeError(
            f"I2C communication failed when configuring BMP280 at address 0x{addr:02X} on bus {BUS_NUMBER}."
        ) from e

    # Temperature calibration
    dig_T1 = get_ushort(cal, 0)
    dig_T2 = get_short(cal, 2)
    dig_T3 = get_short(cal, 4)

    # Pressure calibration
    dig_P1 = get_ushort(cal, 6)
    dig_P2 = get_short(cal, 8)
    dig_P3 = get_short(cal, 10)
    dig_P4 = get_short(cal, 12)
    dig_P5 = get_short(cal, 14)
    dig_P6 = get_short(cal, 16)
    dig_P7 = get_short(cal, 18)
    dig_P8 = get_short(cal, 20)
    dig_P9 = get_short(cal, 22)

    if dig_P1 == 0:
        raise RuntimeError("Invalid calibration data: dig_P1 is 0")

    # Wait for measurement to complete
    wait_time_ms = 1.25 + (2.3 * OVERSAMPLE_TEMP) + ((2.3 * OVERSAMPLE_PRES) + 0.575)
    time.sleep(wait_time_ms / 1000.0)

    try:
        data = bus.read_i2c_block_data(addr, REG_DATA, 6)
    except OSError as e:
        raise RuntimeError(
            f"I2C communication failed when reading measurement data from BMP280 at address 0x{addr:02X} "
            f"on bus {BUS_NUMBER}."
        ) from e

    pres_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
    temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)

    # Temperature compensation
    var1 = ((((temp_raw >> 3) - (dig_T1 << 1))) * dig_T2) >> 11
    var2 = (((((temp_raw >> 4) - dig_T1) * ((temp_raw >> 4) - dig_T1)) >> 12) * dig_T3) >> 14
    t_fine = var1 + var2
    temperature = ((t_fine * 5 + 128) >> 8) / 100.0

    # Pressure compensation
    var1 = t_fine / 2.0 - 64000.0
    var2 = var1 * var1 * dig_P6 / 32768.0
    var2 = var2 + var1 * dig_P5 * 2.0
    var2 = var2 / 4.0 + dig_P4 * 65536.0
    var1 = (dig_P3 * var1 * var1 / 524288.0 + dig_P2 * var1) / 524288.0
    var1 = (1.0 + var1 / 32768.0) * dig_P1

    if var1 == 0:
        raise RuntimeError("Pressure calculation failed because var1 became 0")

    pressure = 1048576.0 - pres_raw
    pressure = ((pressure - var2 / 4096.0) * 6250.0) / var1
    var1 = dig_P9 * pressure * pressure / 2147483648.0
    var2 = pressure * dig_P8 / 32768.0
    pressure = pressure + (var1 + var2 + dig_P7) / 16.0
    pressure_hpa = pressure / 100.0

    return temperature, pressure_hpa


def estimate_altitude(pressure_hpa, sea_level_pressure_hpa=SEA_LEVEL_PRESSURE_HPA):
    """
    Estimate altitude in meters from pressure.
    This is only an approximation.
    """
    if pressure_hpa <= 0 or sea_level_pressure_hpa <= 0:
        return None
    altitude = 44330.0 * (1.0 - (pressure_hpa / sea_level_pressure_hpa) ** (1.0 / 5.255))
    return altitude


def main():
    print("=== BMP280 Test ===")
    print(f"Using I2C bus {BUS_NUMBER} and device address 0x{DEVICE_ADDRESS:02X}")
    print("Make sure the BMP280 is connected to the I2C bus and I2C is enabled (raspi-config).")
    print()

    try:
        chip_id, chip_version = read_chip_id()
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        print("Hint: You can use 'sudo i2cdetect -y 1' to scan for I2C devices on bus 1.")
        sys.exit(1)

    print(f"Sensor detected: chip ID = 0x{chip_id:02X}, version = 0x{chip_version:02X}")

    if chip_id not in (0x56, 0x57, 0x58):
        print("[ERROR] Detected chip is not a BMP280.")
        print("        BMP280 chip IDs are usually 0x56, 0x57 or 0x58.")
        print("        BME280 uses chip ID 0x60.")
        sys.exit(1)

    try:
        temperature, pressure = read_bmp280_all()
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    altitude = estimate_altitude(pressure)
    now = datetime.datetime.now().isoformat(timespec="seconds")

    print()
    print(f"Timestamp   : {now}")
    print(f"Temperature : {temperature:.2f} deg C")
    print(f"Pressure    : {pressure:.2f} hPa")
    if altitude is not None:
        print(f"Altitude    : {altitude:.2f} m (estimated, based on {SEA_LEVEL_PRESSURE_HPA:.2f} hPa sea level)")
    else:
        print("Altitude    : n/a")
    print()
    print("Test finished. Exiting.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting.")
        sys.exit(0)
    except Exception as exc:
        print(f"[UNEXPECTED ERROR] {exc}")
        sys.exit(1)
