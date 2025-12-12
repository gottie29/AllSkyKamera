#!/usr/bin/env python3
"""
AllSkyKamera sensor test script

This script runs a one-shot test for all supported sensors:

- DHT22 / DHT11 on GPIO D6 (Pin 31) via adafruit_dht (board.D6)
- DS18B20 via 1-Wire (/sys/bus/w1/devices/28-*)
- BME280 via I2C bus 1, address 0x76 (smbus)
- HTU21 / GY-21 (Si7021/HTU21D) via I2C bus 1, address 0x40 (smbus)
- SHT3x (SHT30 / SHT31 / SHT35) via I2C bus 1, address 0x44 (smbus)
- MLX90614 via I2C bus 1, address 0x5A (smbus)
- TSL2591 via I2C bus 1 on SCL/SDA (busio + adafruit_tsl2591)

Each sensor is tested once. Errors are caught so the script always runs
to completion and prints a final summary.
"""

import time
import math
import os
import glob
import datetime
import statistics

# --------------------------------------------------------------------
# Optional imports / flags
# --------------------------------------------------------------------

# board / CircuitPython
try:
    import board
except ImportError:
    board = None  # placeholder

# DHT
try:
    import adafruit_dht
    HAVE_DHT = board is not None
except ImportError:
    HAVE_DHT = False

# SMBus (for BME280 + HTU21 + SHT3x + MLX90614)
try:
    import smbus
    HAVE_SMBUS = True
except ImportError:
    HAVE_SMBUS = False

# TSL2591
try:
    import busio
    import adafruit_tsl2591
    HAVE_TSL = board is not None
except ImportError:
    HAVE_TSL = False

# Global I2C bus (initialized on demand)
bus = None

from ctypes import c_short  # for signed conversion

# --------------------------------------------------------------------
# DHT22 / DHT11 (on D6)
# --------------------------------------------------------------------

DHT_GPIO = getattr(board, "D6", None) if board is not None else None


def _read_dht(sensor_class, retries=10, delay=0.3, t_min=-40.0, t_max=80.0):
    """
    Read DHT sensor multiple times, filter out invalid values,
    and return median temperature and humidity.
    """
    temps, hums = [], []

    try:
        dht = sensor_class(DHT_GPIO, use_pulseio=False)
    except Exception as e:
        print(f"  ERROR: Could not initialize DHT sensor: {e}")
        return None, None

    # Give the sensor some time to wake up
    time.sleep(2.0)

    try:
        for _ in range(retries):
            try:
                t = dht.temperature
                h = dht.humidity
                if (
                    t is not None
                    and h is not None
                    and t_min <= t <= t_max
                    and 0.0 <= h <= 100.0
                ):
                    temps.append(float(t))
                    hums.append(float(h))
            except RuntimeError:
                # Typical DHT glitch, ignore and retry
                pass
            except Exception as e:
                print(f"  WARNING: Single DHT read error: {e}")
            time.sleep(delay)
    finally:
        try:
            dht.exit()
        except Exception:
            pass

    if temps and hums:
        return statistics.median(temps), statistics.median(hums)
    return None, None


def test_dht(summary=None):
    sensor_key = "DHT"
    print("=== DHT22 / DHT11 Test ===")
    print("Interface: GPIO D6 (board.D6) via adafruit_dht\n")

    if not HAVE_DHT:
        msg = (
            "DHT libraries (adafruit_dht / board) are not installed "
            "or the 'board' module is not available.\n"
            "Install with:\n"
            "  sudo pip3 install adafruit-circuitpython-dht adafruit-blinka"
        )
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "unavailable", "details": msg}
        print()
        return

    if DHT_GPIO is None:
        msg = "No GPIO configured for DHT (board.D6 not available)."
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "unavailable", "details": msg}
        print()
        return

    # Try DHT22 first
    try:
        print("Trying DHT22 on D6 ...")
        t, h = _read_dht(adafruit_dht.DHT22, t_min=-40.0, t_max=80.0)
        if t is not None:
            msg = f"DHT22 OK: {t:.1f} C, {h:.1f} % RH"
            print(msg)
            if summary is not None:
                summary["sensors"][sensor_key] = {"status": "OK", "details": msg}
            print()
            return
    except Exception as e:
        print(f"  ERROR: Unexpected error while testing DHT22: {e}")

    # Fallback: DHT11
    try:
        print("No valid DHT22 values, trying DHT11 on D6 ...")
        t, h = _read_dht(adafruit_dht.DHT11, t_min=-20.0, t_max=60.0)
        if t is not None:
            msg = f"DHT11 OK: {t:.1f} C, {h:.1f} % RH"
            print(msg)
            if summary is not None:
                summary["sensors"][sensor_key] = {"status": "OK", "details": msg}
        else:
            msg = "No working DHT22/DHT11 detected."
            print(msg)
            if summary is not None:
                summary["sensors"][sensor_key] = {"status": "not found", "details": msg}
    except Exception as e:
        msg = f"ERROR: Unexpected error while testing DHT11: {e}"
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "error", "details": msg}
    print()


# --------------------------------------------------------------------
# DS18B20 (1-Wire)
# --------------------------------------------------------------------

def read_ds18b20():
    base_dir = "/sys/bus/w1/devices/"
    device_folders = glob.glob(base_dir + "28-*")
    if not device_folders:
        return None, "No DS18B20 sensor found (is 1-Wire enabled in raspi-config?)."

    device_file = os.path.join(device_folders[0], "w1_slave")

    try:
        with open(device_file, "r") as f:
            lines = f.readlines()

        if not lines:
            return None, "Empty response from DS18B20."

        if lines[0].strip()[-3:] != "YES":
            return None, "CRC error while reading DS18B20 (first line does not end with YES)."

        equals_pos = lines[1].find("t=")
        if equals_pos != -1:
            temp_string = lines[1][equals_pos + 2 :].strip()
            temperature_c = float(temp_string) / 1000.0
            return temperature_c, None
        else:
            return None, "Temperature field 't=' not found in DS18B20 data."
    except FileNotFoundError:
        return None, "DS18B20 file not found (load w1-gpio and w1-therm modules?)."
    except Exception as e:
        return None, f"ERROR: {e}"


def test_ds18b20(summary=None):
    sensor_key = "DS18B20"
    print("=== DS18B20 Test ===")
    print("Interface: 1-Wire via /sys/bus/w1/devices (28-*)\n")

    temp, err = read_ds18b20()
    if err:
        print(err)
        if summary is not None:
            status = "error"
            if "No DS18B20" in err or "not found" in err:
                status = "not found"
            summary["sensors"][sensor_key] = {"status": status, "details": err}
    else:
        msg = f"Temperature: {temp:.2f} C"
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "OK", "details": msg}
    print()


# --------------------------------------------------------------------
# BME280 (I2C, 0x76)
# --------------------------------------------------------------------

DEVICE_BME = 0x76


def _getShort(data, index):
    return c_short((data[index + 1] << 8) + data[index]).value


def _getUShort(data, index):
    return (data[index + 1] << 8) + data[index]


def _getChar(data, index):
    result = data[index]
    if result > 127:
        result -= 256
    return result


def _getUChar(data, index):
    return data[index] & 0xFF


def readBME280All(addr=DEVICE_BME):
    """
    Low-level readout of BME280 via SMBus.
    Returns (temperature_C, pressure_hPa, humidity_percent).
    """
    global bus

    REG_DATA = 0xF7
    REG_CONTROL = 0xF4
    REG_CONFIG = 0xF5
    REG_CONTROL_HUM = 0xF2
    OVERSAMPLE_TEMP = 2
    OVERSAMPLE_PRES = 2
    MODE = 1
    OVERSAMPLE_HUM = 2

    # Humidity oversampling
    bus.write_byte_data(addr, REG_CONTROL_HUM, OVERSAMPLE_HUM)
    # Temperature + pressure oversampling + mode
    control = OVERSAMPLE_TEMP << 5 | OVERSAMPLE_PRES << 2 | MODE
    bus.write_byte_data(addr, REG_CONTROL, control)

    # Calibration data
    cal1 = bus.read_i2c_block_data(addr, 0x88, 24)
    cal2 = bus.read_i2c_block_data(addr, 0xA1, 1)
    cal3 = bus.read_i2c_block_data(addr, 0xE1, 7)

    dig_T1 = _getUShort(cal1, 0)
    dig_T2 = _getShort(cal1, 2)
    dig_T3 = _getShort(cal1, 4)

    dig_P1 = _getUShort(cal1, 6)
    dig_P2 = _getShort(cal1, 8)
    dig_P3 = _getShort(cal1, 10)
    dig_P4 = _getShort(cal1, 12)
    dig_P5 = _getShort(cal1, 14)
    dig_P6 = _getShort(cal1, 16)
    dig_P7 = _getShort(cal1, 18)
    dig_P8 = _getShort(cal1, 20)
    dig_P9 = _getShort(cal1, 22)

    dig_H1 = _getUChar(cal2, 0)
    dig_H2 = _getShort(cal3, 0)
    dig_H3 = _getUChar(cal3, 2)

    dig_H4 = _getChar(cal3, 3)
    dig_H4 = (dig_H4 << 24) >> 20
    dig_H4 |= _getChar(cal3, 4) & 0x0F

    dig_H5 = _getChar(cal3, 5)
    dig_H5 = (dig_H5 << 24) >> 20
    dig_H5 |= _getUChar(cal3, 4) >> 4 & 0x0F

    dig_H6 = _getChar(cal3, 6)

    wait_time = (
        1.25
        + (2.3 * OVERSAMPLE_TEMP)
        + ((2.3 * OVERSAMPLE_PRES) + 0.575)
        + ((2.3 * OVERSAMPLE_HUM) + 0.575)
    )
    time.sleep(wait_time / 1000.0)

    data = bus.read_i2c_block_data(addr, REG_DATA, 8)
    pres_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
    temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
    hum_raw = (data[6] << 8) | data[7]

    # Temperature
    var1 = (((temp_raw >> 3) - (dig_T1 << 1)) * dig_T2) >> 11
    var2 = (
        (((temp_raw >> 4) - dig_T1) * ((temp_raw >> 4) - dig_T1) >> 12) * dig_T3
    ) >> 14
    t_fine = var1 + var2
    temperature = float(((t_fine * 5) + 128) >> 8)

    # Pressure
    var1 = t_fine / 2.0 - 64000.0
    var2 = var1 * var1 * dig_P6 / 32768.0
    var2 = var2 + var1 * dig_P5 * 2.0
    var2 = var2 / 4.0 + dig_P4 * 65536.0
    var1 = (dig_P3 * var1 * var1 / 524288.0 + dig_P2 * var1) / 524288.0
    var1 = (1.0 + var1 / 32768.0) * dig_P1

    if var1 == 0:
        pressure = 0
    else:
        pressure = 1048576.0 - pres_raw
        pressure = ((pressure - var2 / 4096.0) * 6250.0) / var1
        var1 = dig_P9 * pressure * pressure / 2147483648.0
        var2 = pressure * dig_P8 / 32768.0
        pressure = pressure + (var1 + var2 + dig_P7) / 16.0

    # Humidity
    humidity = t_fine - 76800.0
    humidity = (
        (hum_raw - (dig_H4 * 64.0 + dig_H5 / 16384.0 * humidity))
        * (
            dig_H2
            / 65536.0
            * (
                1.0
                + dig_H6
                / 67108864.0
                * humidity
                * (1.0 + dig_H3 / 67108864.0 * humidity)
            )
        )
    )
    humidity = humidity * (1.0 - dig_H1 * humidity / 524288.0)
    humidity = max(0, min(humidity, 100))

    return temperature / 100.0, pressure / 100.0, humidity


def dew_point(temp, hum):
    # Magnus formula
    a = 17.62
    b = 243.12
    alpha = ((a * temp) / (b + temp)) + math.log(hum / 100.0)
    return (b * alpha) / (a - alpha)


def test_bme280(summary=None):
    sensor_key = "BME280"
    print("=== BME280 Test ===")
    print("Interface: I2C bus 1, address 0x76 via smbus\n")

    if not HAVE_SMBUS:
        msg = (
            "Python smbus module is not installed. BME280 cannot be read.\n"
            "Install with:\n"
            "  sudo apt-get install python3-smbus\n"
            "or (alternative):\n"
            "  sudo pip3 install smbus2"
        )
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "unavailable", "details": msg}
        print()
        return

    global bus
    try:
        if bus is None:
            bus = smbus.SMBus(1)
    except Exception as e:
        msg = (
            "ERROR: Could not open I2C bus 1 using smbus.SMBus(1).\n"
            "Is I2C enabled in 'sudo raspi-config'?\n"
            f"Exception: {e}"
        )
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "error", "details": msg}
        print()
        return

    try:
        temperature, pressure, humidity = readBME280All()
    except OSError as e:
        msg = (
            "ERROR: No BME280 reachable at address 0x76 or I2C error occurred.\n"
            f"Exception: {e}"
        )
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "not found", "details": msg}
        print()
        return
    except Exception as e:
        msg = f"ERROR: Failed to read BME280: {e}"
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "error", "details": msg}
        print()
        return

    td = dew_point(temperature, humidity)
    msg_lines = [
        f"Temperature : {temperature:.2f} C",
        f"Pressure    : {pressure:.2f} hPa",
        f"Humidity    : {humidity:.2f} %",
        f"Dew point   : {td:.2f} C",
    ]
    for line in msg_lines:
        print(line)
    if summary is not None:
        summary["sensors"][sensor_key] = {
            "status": "OK",
            "details": "; ".join(msg_lines),
        }
    print()


# --------------------------------------------------------------------
# HTU21 / GY-21 (Si7021 / HTU21D, I2C, 0x40)
# --------------------------------------------------------------------

DEVICE_HTU = 0x40
CMD_HTU_TEMP_HOLD = 0xE3  # Measure Temperature, Hold Master
CMD_HTU_HUM_HOLD  = 0xE5  # Measure Humidity, Hold Master


def readHTU21All(addr=DEVICE_HTU):
    """
    Read temperature (C) and humidity (% RH) from HTU21 / GY-21
    using Hold-Master mode: read_i2c_block_data(addr, command, 2).
    """
    global bus

    # Temperature
    data_t = bus.read_i2c_block_data(addr, CMD_HTU_TEMP_HOLD, 2)
    raw_t = (data_t[0] << 8) | data_t[1]
    raw_t &= 0xFFFC
    temp_c = -46.85 + (175.72 * raw_t / 65536.0)

    time.sleep(0.02)

    # Humidity
    data_h = bus.read_i2c_block_data(addr, CMD_HTU_HUM_HOLD, 2)
    raw_h = (data_h[0] << 8) | data_h[1]
    raw_h &= 0xFFFC
    rh = -6.0 + (125.0 * raw_h / 65536.0)
    rh = max(0.0, min(100.0, rh))

    return temp_c, rh


def test_htu21(summary=None):
    sensor_key = "HTU21"
    print("=== HTU21 / GY-21 (Si7021 / HTU21D) Test ===")
    print("Interface: I2C bus 1, address 0x40 via smbus (Hold-Master mode)\n")

    if not HAVE_SMBUS:
        msg = (
            "Python smbus module is not installed. HTU21/GY-21 cannot be read.\n"
            "Install with:\n"
            "  sudo apt-get install python3-smbus\n"
            "or (alternative):\n"
            "  sudo pip3 install smbus2"
        )
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "unavailable", "details": msg}
        print()
        return

    global bus
    try:
        if bus is None:
            bus = smbus.SMBus(1)
    except Exception as e:
        msg = (
            "ERROR: Could not open I2C bus 1 using smbus.SMBus(1).\n"
            "Is I2C enabled in 'sudo raspi-config'?\n"
            f"Exception: {e}"
        )
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "error", "details": msg}
        print()
        return

    try:
        temp_c, rh = readHTU21All()
    except OSError as e:
        msg = (
            "I2C error while talking to HTU21/GY-21 "
            "(sensor not found on address 0x40?).\n"
            f"Exception: {e}"
        )
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "not found", "details": msg}
        print()
        return
    except Exception as e:
        msg = f"Unexpected error while reading HTU21/GY-21: {e}"
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "error", "details": msg}
        print()
        return

    td = dew_point(temp_c, rh)
    msg_lines = [
        f"Temperature : {temp_c:.2f} C",
        f"Humidity    : {rh:.2f} % RH",
        f"Dew point   : {td:.2f} C",
    ]
    for line in msg_lines:
        print(line)
    if summary is not None:
        summary["sensors"][sensor_key] = {
            "status": "OK",
            "details": "; ".join(msg_lines),
        }
    print()


# --------------------------------------------------------------------
# SHT3x (SHT30 / SHT31 / SHT35, I2C, 0x44)
# --------------------------------------------------------------------

DEVICE_SHT = 0x44  # default address for SHT3x
CMD_SHT_SINGLE_SHOT = (0x24, 0x00)  # High repeatability, no clock stretching


def readSHT3xAll(addr=DEVICE_SHT):
    """
    Read temperature (C) and humidity (% RH) from SHT3x using a
    single-shot measurement (no clock stretching).
    """
    global bus

    # Send single-shot command
    bus.write_i2c_block_data(addr, CMD_SHT_SINGLE_SHOT[0], [CMD_SHT_SINGLE_SHOT[1]])

    time.sleep(0.020)

    # Read 6 bytes: T_MSB, T_LSB, T_CRC, H_MSB, H_LSB, H_CRC
    data = bus.read_i2c_block_data(addr, 0x00, 6)
    if len(data) != 6:
        raise RuntimeError(f"Unexpected SHT3x data length: {len(data)}, expected 6")

    raw_t = (data[0] << 8) | data[1]
    raw_h = (data[3] << 8) | data[4]

    temp_c = -45.0 + (175.0 * (raw_t / 65535.0))
    hum = 100.0 * (raw_h / 65535.0)
    hum = max(0.0, min(100.0, hum))

    return round(temp_c, 2), round(hum, 2)


def test_sht3x(summary=None):
    sensor_key = "SHT3x"
    print("=== SHT3x Test (SHT30 / SHT31 / SHT35) ===")
    print("Interface: I2C bus 1, address 0x44 via smbus\n")

    if not HAVE_SMBUS:
        msg = (
            "Python smbus module is not installed. SHT3x cannot be read.\n"
            "Install with:\n"
            "  sudo apt-get install python3-smbus\n"
            "or (alternative):\n"
            "  sudo pip3 install smbus2"
        )
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "unavailable", "details": msg}
        print()
        return

    global bus
    try:
        if bus is None:
            bus = smbus.SMBus(1)
    except Exception as e:
        msg = (
            "ERROR: Could not open I2C bus 1 using smbus.SMBus(1).\n"
            "Is I2C enabled in 'sudo raspi-config'?\n"
            f"Exception: {e}"
        )
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "error", "details": msg}
        print()
        return

    try:
        temp_c, hum = readSHT3xAll()
    except OSError as e:
        msg = (
            "I2C error while talking to SHT3x "
            "(sensor not found on address 0x44?).\n"
            f"Exception: {e}"
        )
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "not found", "details": msg}
        print()
        return
    except Exception as e:
        msg = f"Unexpected error while reading SHT3x: {e}"
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "error", "details": msg}
        print()
        return

    td = dew_point(temp_c, hum)
    msg_lines = [
        f"Temperature : {temp_c:.2f} C",
        f"Humidity    : {hum:.2f} % RH",
        f"Dew point   : {td:.2f} C",
    ]
    for line in msg_lines:
        print(line)
    if summary is not None:
        summary["sensors"][sensor_key] = {
            "status": "OK",
            "details": "; ".join(msg_lines),
        }
    print()


# --------------------------------------------------------------------
# MLX90614 (I2C, 0x5A)
# --------------------------------------------------------------------

DEVICE_MLX = 0x5A


def crc8(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ 0x07
            else:
                crc <<= 1
            crc &= 0xFF
    return crc


def read_raw_pec(addr, reg, check_pec=False):
    global bus
    data = bus.read_i2c_block_data(addr, reg, 3)
    lsb, msb, pec_rx = data[0], data[1], data[2]
    raw = (msb << 8) | lsb

    if check_pec:
        pkt = [(addr << 1) | 0, reg, (addr << 1) | 1, lsb, msb]
        pec_calc = crc8(pkt)
        if pec_calc != pec_rx:
            raise ValueError(
                f"PEC mismatch (got {pec_rx:#04x}, expected {pec_calc:#04x})"
            )
    return raw


def raw_to_celsius(raw):
    return (raw * 0.02) - 273.15


def read_mlx_temperature(addr, reg, check_pec=False):
    raw = read_raw_pec(addr, reg, check_pec=check_pec)
    t = raw_to_celsius(raw)

    if not (-70.0 <= t <= 380.0):
        swapped = ((raw & 0xFF) << 8) | (raw >> 8)
        t_swapped = raw_to_celsius(swapped)
        if -70.0 <= t_swapped <= 380.0:
            t = t_swapped
    return round(t, 2)


def test_mlx90614(summary=None):
    sensor_key = "MLX90614"
    print("=== MLX90614 Test ===")
    print("Interface: I2C bus 1, address 0x5A via smbus\n")

    if not HAVE_SMBUS:
        msg = (
            "Python smbus module is not installed. MLX90614 cannot be read.\n"
            "Install with:\n"
            "  sudo apt-get install python3-smbus\n"
            "or (alternative):\n"
            "  sudo pip3 install smbus2"
        )
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "unavailable", "details": msg}
        print()
        return

    global bus
    try:
        if bus is None:
            bus = smbus.SMBus(1)
    except Exception as e:
        msg = (
            "ERROR: Could not open I2C bus 1 using smbus.SMBus(1).\n"
            "Is I2C enabled in 'sudo raspi-config'?\n"
            f"Exception: {e}"
        )
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "error", "details": msg}
        print()
        return

    REG_TA = 0x06
    REG_TOBJ1 = 0x07

    try:
        ta = read_mlx_temperature(DEVICE_MLX, REG_TA, check_pec=False)
        tobj1 = read_mlx_temperature(DEVICE_MLX, REG_TOBJ1, check_pec=False)
        msg1 = f"Ambient : {ta:.2f} C"
        msg2 = f"Object  : {tobj1:.2f} C"
        print(msg1)
        print(msg2)
        if summary is not None:
            summary["sensors"][sensor_key] = {
                "status": "OK",
                "details": f"{msg1}; {msg2}",
            }
    except OSError as e:
        msg = (
            "I2C error while talking to MLX90614 (is it really on address 0x5A?).\n"
            f"Exception: {e}"
        )
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "not found", "details": msg}
    except ValueError as e:
        msg = f"Data error (PEC or format) while reading MLX90614: {e}"
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "error", "details": msg}
    except Exception as e:
        msg = f"Unexpected error while testing MLX90614: {e}"
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "error", "details": msg}
    print()


# --------------------------------------------------------------------
# TSL2591 (I2C)
# --------------------------------------------------------------------

def safe_value(x, fallback=0.0001):
    if x is None or x <= 0:
        return fallback
    return float(x)


def test_tsl2591(summary=None):
    sensor_key = "TSL2591"
    print("=== TSL2591 Test ===")
    print("Interface: I2C bus 1 on SCL/SDA via busio + adafruit_tsl2591\n")

    if not HAVE_TSL:
        msg = (
            "TSL2591 libraries (busio / adafruit_tsl2591) or the 'board' module\n"
            "are not installed or not available.\n"
            "Install with:\n"
            "  sudo pip3 install adafruit-blinka adafruit-circuitpython-tsl2591"
        )
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "unavailable", "details": msg}
        print()
        return

    if board is None:
        msg = (
            "The 'board' module is not available. Cannot determine I2C pins.\n"
            "Make sure Adafruit Blinka is installed and running on a supported platform."
        )
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "unavailable", "details": msg}
        print()
        return

    try:
        i2c = busio.I2C(board.SCL, board.SDA)
    except Exception as e:
        msg = (
            "ERROR: Could not initialize I2C via busio.I2C(board.SCL, board.SDA).\n"
            "Is I2C enabled in 'sudo raspi-config'?\n"
            f"Exception: {e}"
        )
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "error", "details": msg}
        print()
        return

    try:
        sensor = adafruit_tsl2591.TSL2591(i2c)

        lux = safe_value(sensor.lux)
        visible = safe_value(sensor.visible)
        infrared = safe_value(sensor.infrared)
        full = safe_value(sensor.full_spectrum)

        skybright = 22.0 - 2.5 * math.log10(lux)
        skybright2 = 22.0 - 2.5 * math.log10(visible)
        if skybright2 < 6.0:
            skybright2 = 0.0001

        msg_lines = [
            f"Lux          : {lux:.2f} lx",
            f"Visible      : {visible:.2f}",
            f"Infrared     : {infrared:.2f}",
            f"Full spectrum: {full:.2f}",
            f"Sky brightness (mag/arcsec^2) total : {skybright:.2f}",
            f"Sky brightness (mag/arcsec^2) vis   : {skybright2:.2f}",
        ]
        for line in msg_lines:
            print(line)
        if summary is not None:
            summary["sensors"][sensor_key] = {
                "status": "OK",
                "details": "; ".join(msg_lines),
            }
    except OSError as e:
        msg = (
            "I2C error while talking to TSL2591 (sensor not found on bus?).\n"
            f"Exception: {e}"
        )
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "not found", "details": msg}
    except Exception as e:
        msg = f"Unexpected error while testing TSL2591: {e}"
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "error", "details": msg}
    print()


# --------------------------------------------------------------------
# Bus checks: I2C and 1-Wire
# --------------------------------------------------------------------

def test_i2c_bus(summary=None):
    bus_key = "i2c"
    print("=== I2C Bus Test ===")
    print("Checks for /dev/i2c-1 and smbus availability.\n")

    dev_path = "/dev/i2c-1"
    if not os.path.exists(dev_path):
        msg = (
            "/dev/i2c-1 does not exist. I2C is probably not enabled.\n"
            "Enable it via:\n"
            "  sudo raspi-config  -> Interface Options -> I2C"
        )
        print(msg)
        if summary is not None:
            summary["buses"][bus_key] = {"status": "unavailable", "details": msg}
        print()
        return

    if not HAVE_SMBUS:
        msg = (
            "Python smbus module is not installed. I2C cannot be used from Python.\n"
            "Install with:\n"
            "  sudo apt-get install python3-smbus\n"
            "or (alternative):\n"
            "  sudo pip3 install smbus2"
        )
        print(msg)
        if summary is not None:
            summary["buses"][bus_key] = {"status": "unavailable", "details": msg}
        print()
        return

    try:
        tmp = smbus.SMBus(1)
        tmp.close()
        msg = "/dev/i2c-1 is present and smbus.SMBus(1) could be opened."
        print(msg)
        if summary is not None:
            summary["buses"][bus_key] = {"status": "OK", "details": msg}
    except Exception as e:
        msg = (
            "/dev/i2c-1 exists, but opening it with smbus.SMBus(1) failed.\n"
            f"Exception: {e}"
        )
        print(msg)
        if summary is not None:
            summary["buses"][bus_key] = {"status": "error", "details": msg}
    print()


def test_onewire_bus(summary=None):
    bus_key = "onewire"
    print("=== 1-Wire Bus Test ===")
    print("Checks /sys/bus/w1/devices for master and DS18B20 devices.\n")

    base_dir = "/sys/bus/w1/devices"
    if not os.path.isdir(base_dir):
        msg = (
            f"{base_dir} does not exist. 1-Wire is probably not enabled.\n"
            "Enable it via:\n"
            "  sudo raspi-config  -> Interface Options -> 1-Wire"
        )
        print(msg)
        if summary is not None:
            summary["buses"][bus_key] = {"status": "unavailable", "details": msg}
        print()
        return

    try:
        entries = os.listdir(base_dir)
    except Exception as e:
        msg = f"Could not read directory {base_dir}: {e}"
        print(msg)
        if summary is not None:
            summary["buses"][bus_key] = {"status": "error", "details": msg}
        print()
        return

    masters = [e for e in entries if e.startswith("w1_bus_master")]
    devices = [e for e in entries if e.startswith("28-")]

    if masters:
        msg = "1-Wire master found: " + ", ".join(masters)
        print(msg)
        if devices:
            msg2 = "Connected 1-Wire devices: " + ", ".join(devices)
            print(msg2)
            combined = msg + "; " + msg2
        else:
            msg2 = "No DS18B20 (28-*) found, but the bus is active."
            print(msg2)
            combined = msg + "; " + msg2
        if summary is not None:
            summary["buses"][bus_key] = {"status": "OK", "details": combined}
    else:
        msg = "No w1_bus_master* found. 1-Wire does not seem to be active."
        print(msg)
        if summary is not None:
            summary["buses"][bus_key] = {"status": "not found", "details": msg}
    print()


# --------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------

def print_summary(summary):
    print("===================================================")
    print("  Summary")
    print("===================================================")

    buses = summary.get("buses", {})
    sensors = summary.get("sensors", {})

    print("\nBus interfaces:")
    for key, label in [("i2c", "I2C"), ("onewire", "1-Wire")]:
        info = buses.get(key)
        if info is None:
            print(f"- {label}: not tested")
        else:
            print(f"- {label}: {info.get('status', 'unknown')} - {info.get('details', '')}")

    print("\nSensors:")
    sensor_labels = [
        ("DHT", "DHT22/DHT11"),
        ("DS18B20", "DS18B20"),
        ("BME280", "BME280"),
        ("HTU21", "HTU21 / GY-21"),
        ("SHT3x", "SHT3x"),
        ("MLX90614", "MLX90614"),
        ("TSL2591", "TSL2591"),
    ]
    for key, label in sensor_labels:
        info = sensors.get(key)
        if info is None:
            print(f"- {label}: not tested")
        else:
            print(f"- {label}: {info.get('status', 'unknown')} - {info.get('details', '')}")

    ok_sensors = [k for k, v in sensors.items() if v.get("status") == "OK"]
    problem_sensors = [k for k, v in sensors.items() if v.get("status") != "OK"]

    print("\nOverall:")
    print(f"- OK sensors      : {len(ok_sensors)} ({', '.join(ok_sensors) or '-'})")
    print(f"- Problem sensors : {len(problem_sensors)} ({', '.join(problem_sensors) or '-'})")


# --------------------------------------------------------------------
# Main
# --------------------------------------------------------------------

def main():
    print("===================================================")
    print("  AllSkyKamera - full sensor test")
    print("  Time: ", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("===================================================\n")

    summary = {"buses": {}, "sensors": {}}

    # Bus checks first
    try:
        test_i2c_bus(summary)
    except Exception as e:
        print(f"[ERROR] test_i2c_bus crashed unexpectedly: {e}\n")
    try:
        test_onewire_bus(summary)
    except Exception as e:
        print(f"[ERROR] test_onewire_bus crashed unexpectedly: {e}\n")

    # Sensor tests (each wrapped to keep script running)
    for fn in (
        test_dht,
        test_ds18b20,
        test_bme280,
        test_htu21,
        test_sht3x,
        test_mlx90614,
        test_tsl2591,
    ):
        try:
            fn(summary)
        except Exception as e:
            print(f"[ERROR] {fn.__name__} crashed unexpectedly: {e}\n")

    print_summary(summary)
    print("\nDone. All available sensors have been tested.")


if __name__ == "__main__":
    main()
