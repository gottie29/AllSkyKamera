#!/usr/bin/env python3
"""
Simple BME280 test script.

- Uses I2C bus 1 and device address 0x76 by default.
- Prints one measurement (temperature, pressure, humidity, dew point) and exits.
- Shows clear error messages if:
  * the smbus library is missing
  * the I2C bus or device cannot be reached
"""

import sys
import time
import math
import datetime

try:
    import smbus  # for I2C access on Raspberry Pi / Linux
except ImportError:
    print("[ERROR] Python module 'smbus' is not installed.")
    print("        Install it with:")
    print("        sudo apt-get update")
    print("        sudo apt-get install python3-smbus i2c-tools")
    sys.exit(1)

from ctypes import c_short, c_byte, c_ubyte

DEVICE_ADDRESS = 0x76
BUS_NUMBER = 1  # I2C bus number (1 is default on modern Raspberry Pi boards)

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


def get_char(data, index):
    result = data[index]
    if result > 127:
        result -= 256
    return result


def get_uchar(data, index):
    return data[index] & 0xFF


def read_bme280_id(addr=DEVICE_ADDRESS):
    """Read chip ID and version from BME280 via I2C."""
    REG_ID = 0xD0
    try:
        chip_id, chip_version = bus.read_i2c_block_data(addr, REG_ID, 2)
    except OSError as e:
        raise RuntimeError(
            f"I2C communication failed when reading BME280 ID at address 0x{addr:02X} on bus {BUS_NUMBER}. "
            "Check wiring, sensor power, and that I2C is enabled."
        ) from e
    return chip_id, chip_version


def read_bme280_all(addr=DEVICE_ADDRESS):
    """Read temperature, pressure and humidity from the BME280 sensor."""
    REG_DATA = 0xF7
    REG_CONTROL = 0xF4
    REG_CONFIG = 0xF5
    REG_CONTROL_HUM = 0xF2

    OVERSAMPLE_TEMP = 2
    OVERSAMPLE_PRES = 2
    OVERSAMPLE_HUM = 2
    MODE = 1  # forced mode

    try:
        # Set humidity oversampling
        bus.write_byte_data(addr, REG_CONTROL_HUM, OVERSAMPLE_HUM)

        # Set control register (temp + pressure oversampling, mode)
        control = (OVERSAMPLE_TEMP << 5) | (OVERSAMPLE_PRES << 2) | MODE
        bus.write_byte_data(addr, REG_CONTROL, control)

        # Read calibration data
        cal1 = bus.read_i2c_block_data(addr, 0x88, 24)
        cal2 = bus.read_i2c_block_data(addr, 0xA1, 1)
        cal3 = bus.read_i2c_block_data(addr, 0xE1, 7)
    except OSError as e:
        raise RuntimeError(
            f"I2C communication failed when configuring BME280 at address 0x{addr:02X} on bus {BUS_NUMBER}."
        ) from e

    # Temperature calibration
    dig_T1 = get_ushort(cal1, 0)
    dig_T2 = get_short(cal1, 2)
    dig_T3 = get_short(cal1, 4)

    # Pressure calibration
    dig_P1 = get_ushort(cal1, 6)
    dig_P2 = get_short(cal1, 8)
    dig_P3 = get_short(cal1, 10)
    dig_P4 = get_short(cal1, 12)
    dig_P5 = get_short(cal1, 14)
    dig_P6 = get_short(cal1, 16)
    dig_P7 = get_short(cal1, 18)
    dig_P8 = get_short(cal1, 20)
    dig_P9 = get_short(cal1, 22)

    # Humidity calibration
    dig_H1 = get_uchar(cal2, 0)
    dig_H2 = get_short(cal3, 0)
    dig_H3 = get_uchar(cal3, 2)

    dig_H4 = get_char(cal3, 3)
    dig_H4 = (dig_H4 << 24) >> 20
    dig_H4 |= get_char(cal3, 4) & 0x0F

    dig_H5 = get_char(cal3, 5)
    dig_H5 = (dig_H5 << 24) >> 20
    dig_H5 |= get_uchar(cal3, 4) >> 4 & 0x0F

    dig_H6 = get_char(cal3, 6)

    # Wait for the measurement to complete
    wait_time_ms = 1.25 + (2.3 * OVERSAMPLE_TEMP) + ((2.3 * OVERSAMPLE_PRES) + 0.575) + (
        (2.3 * OVERSAMPLE_HUM) + 0.575
    )
    time.sleep(wait_time_ms / 1000.0)

    try:
        data = bus.read_i2c_block_data(addr, REG_DATA, 8)
    except OSError as e:
        raise RuntimeError(
            f"I2C communication failed when reading measurement data from BME280 at address 0x{addr:02X} "
            f"on bus {BUS_NUMBER}."
        ) from e

    pres_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
    temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
    hum_raw = (data[6] << 8) | data[7]

    # Temperature compensation
    var1 = ((((temp_raw >> 3) - (dig_T1 << 1))) * dig_T2) >> 11
    var2 = (
        (((temp_raw >> 4) - dig_T1) * ((temp_raw >> 4) - dig_T1)) >> 12
    ) * dig_T3
    var2 >>= 14
    t_fine = var1 + var2
    temperature = float(((t_fine * 5) + 128) >> 8) / 100.0  # deg C

    # Pressure compensation
    var1 = t_fine / 2.0 - 64000.0
    var2 = var1 * var1 * dig_P6 / 32768.0
    var2 = var2 + var1 * dig_P5 * 2.0
    var2 = var2 / 4.0 + dig_P4 * 65536.0
    var1 = (dig_P3 * var1 * var1 / 524288.0 + dig_P2 * var1) / 524288.0
    var1 = (1.0 + var1 / 32768.0) * dig_P1

    if var1 == 0:
        pressure = 0.0
    else:
        pressure = 1048576.0 - pres_raw
        pressure = ((pressure - var2 / 4096.0) * 6250.0) / var1
        var1 = dig_P9 * pressure * pressure / 2147483648.0
        var2 = pressure * dig_P8 / 32768.0
        pressure = pressure + (var1 + var2 + dig_P7) / 16.0
        pressure = pressure / 100.0  # hPa

    # Humidity compensation
    humidity = t_fine - 76800.0
    humidity = (hum_raw - (dig_H4 * 64.0 + dig_H5 / 16384.0 * humidity)) * (
        dig_H2 / 65536.0 * (1.0 + dig_H6 / 67108864.0 * humidity * (1.0 + dig_H3 / 67108864.0 * humidity))
    )
    humidity = humidity * (1.0 - dig_H1 * humidity / 524288.0)
    humidity = max(0.0, min(humidity, 100.0))

    return temperature, pressure, humidity


def calculate_dew_point(temp_c, humidity_percent):
    """Calculate dew point (deg C) from temperature and relative humidity using Magnus formula."""
    a = 17.62
    b = 243.12
    alpha = ((a * temp_c) / (b + temp_c)) + math.log(humidity_percent / 100.0)
    dew_point = (b * alpha) / (a - alpha)
    return round(dew_point, 2)


def main():
    print("=== BME280 Test ===")
    print(f"Using I2C bus {BUS_NUMBER} and device address 0x{DEVICE_ADDRESS:02X}")
    print("Make sure the BME280 is connected to the I2C bus and I2C is enabled (raspi-config).")
    print()

    try:
        chip_id, chip_version = read_bme280_id()
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        print("Hint: You can use 'sudo i2cdetect -y 1' to scan for I2C devices on bus 1.")
        sys.exit(1)

    print(f"Sensor detected: chip ID = 0x{chip_id:02X}, version = 0x{chip_version:02X}")

    try:
        temperature, pressure, humidity = read_bme280_all()
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    dew_point = calculate_dew_point(temperature, humidity)
    now = datetime.datetime.now().isoformat(timespec="seconds")

    print()
    print(f"Timestamp   : {now}")
    print(f"Temperature : {temperature:.2f} deg C")
    print(f"Pressure    : {pressure:.2f} hPa")
    print(f"Humidity    : {humidity:.2f} %")
    print(f"Dew point   : {dew_point:.2f} deg C")
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
