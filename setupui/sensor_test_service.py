#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import glob
import os


def _safe_float(v, default=0.0):
    try:
        return float(str(v).strip().replace(",", "."))
    except Exception:
        return default


def _safe_int(v, default=0):
    try:
        text = str(v).strip().lower()
        if text.startswith("0x"):
            return int(text, 16)
        return int(text)
    except Exception:
        return default


def test_bme280(address):
    addr = _safe_int(address, 0x76)

    try:
        import time
        import math
        import smbus
        from ctypes import c_short

        BUS_NUMBER = 1
        bus = smbus.SMBus(BUS_NUMBER)

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

        # Chip-ID lesen
        try:
            chip_id, chip_version = bus.read_i2c_block_data(addr, 0xD0, 2)
        except OSError as e:
            return {
                "ok": False,
                "error": "I2C communication failed when reading BME280 ID at address 0x%02X on bus %d: %s" % (
                    addr, BUS_NUMBER, str(e)
                )
            }

        # Optional: BME280 hat typischerweise ID 0x60
        if chip_id != 0x60:
            return {
                "ok": False,
                "error": "Unexpected chip ID 0x%02X at address 0x%02X (expected 0x60 for BME280)" % (
                    chip_id, addr
                )
            }

        REG_DATA = 0xF7
        REG_CONTROL = 0xF4
        REG_CONTROL_HUM = 0xF2

        OVERSAMPLE_TEMP = 2
        OVERSAMPLE_PRES = 2
        OVERSAMPLE_HUM = 2
        MODE = 1  # forced mode

        try:
            bus.write_byte_data(addr, REG_CONTROL_HUM, OVERSAMPLE_HUM)
            control = (OVERSAMPLE_TEMP << 5) | (OVERSAMPLE_PRES << 2) | MODE
            bus.write_byte_data(addr, REG_CONTROL, control)

            cal1 = bus.read_i2c_block_data(addr, 0x88, 24)
            cal2 = bus.read_i2c_block_data(addr, 0xA1, 1)
            cal3 = bus.read_i2c_block_data(addr, 0xE1, 7)
        except OSError as e:
            return {
                "ok": False,
                "error": "I2C communication failed when configuring BME280 at address 0x%02X on bus %d: %s" % (
                    addr, BUS_NUMBER, str(e)
                )
            }

        dig_T1 = get_ushort(cal1, 0)
        dig_T2 = get_short(cal1, 2)
        dig_T3 = get_short(cal1, 4)

        dig_P1 = get_ushort(cal1, 6)
        dig_P2 = get_short(cal1, 8)
        dig_P3 = get_short(cal1, 10)
        dig_P4 = get_short(cal1, 12)
        dig_P5 = get_short(cal1, 14)
        dig_P6 = get_short(cal1, 16)
        dig_P7 = get_short(cal1, 18)
        dig_P8 = get_short(cal1, 20)
        dig_P9 = get_short(cal1, 22)

        dig_H1 = get_uchar(cal2, 0)
        dig_H2 = get_short(cal3, 0)
        dig_H3 = get_uchar(cal3, 2)

        dig_H4 = get_char(cal3, 3)
        dig_H4 = (dig_H4 << 24) >> 20
        dig_H4 |= get_char(cal3, 4) & 0x0F

        dig_H5 = get_char(cal3, 5)
        dig_H5 = (dig_H5 << 24) >> 20
        dig_H5 |= (get_uchar(cal3, 4) >> 4) & 0x0F

        dig_H6 = get_char(cal3, 6)

        wait_time_ms = 1.25 + (2.3 * OVERSAMPLE_TEMP) + ((2.3 * OVERSAMPLE_PRES) + 0.575) + ((2.3 * OVERSAMPLE_HUM) + 0.575)
        time.sleep(wait_time_ms / 1000.0)

        try:
            data = bus.read_i2c_block_data(addr, REG_DATA, 8)
        except OSError as e:
            return {
                "ok": False,
                "error": "I2C communication failed when reading measurement data from BME280 at address 0x%02X on bus %d: %s" % (
                    addr, BUS_NUMBER, str(e)
                )
            }

        pres_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        hum_raw = (data[6] << 8) | data[7]

        var1 = ((((temp_raw >> 3) - (dig_T1 << 1))) * dig_T2) >> 11
        var2 = (((((temp_raw >> 4) - dig_T1) * ((temp_raw >> 4) - dig_T1)) >> 12) * dig_T3) >> 14
        t_fine = var1 + var2
        temperature = float(((t_fine * 5) + 128) >> 8) / 100.0

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
            pressure = pressure / 100.0

        humidity = t_fine - 76800.0
        humidity = (hum_raw - (dig_H4 * 64.0 + dig_H5 / 16384.0 * humidity)) * (
            dig_H2 / 65536.0 * (1.0 + dig_H6 / 67108864.0 * humidity * (1.0 + dig_H3 / 67108864.0 * humidity))
        )
        humidity = humidity * (1.0 - dig_H1 * humidity / 524288.0)
        humidity = max(0.0, min(humidity, 100.0))

        dew_point = None
        if humidity > 0:
            a = 17.62
            b = 243.12
            alpha = ((a * temperature) / (b + temperature)) + math.log(humidity / 100.0)
            dew_point = round((b * alpha) / (a - alpha), 2)

        return {
            "ok": True,
            "values": {
                "chip_id": "0x%02X" % chip_id,
                "chip_version": "0x%02X" % chip_version,
                "temperature_c": round(temperature, 2),
                "humidity_pct": round(humidity, 2),
                "pressure_hpa": round(pressure, 2),
                "dew_point_c": dew_point,
                "i2c_bus": BUS_NUMBER,
                "address": "0x%02X" % addr,
            }
        }

    except ImportError:
        return {
            "ok": False,
            "error": "Python module 'smbus' is not installed. Install: sudo apt-get install python3-smbus i2c-tools"
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def test_tsl2591(address):
    addr = _safe_int(address)

    try:
        import board
        import busio
        import adafruit_tsl2591

        i2c = busio.I2C(board.SCL, board.SDA)
        sensor = adafruit_tsl2591.TSL2591(i2c, address=addr)

        return {
            "ok": True,
            "values": {
                "lux": round(float(sensor.lux), 2),
                "infrared": int(sensor.infrared),
                "visible": int(sensor.visible),
                "full_spectrum": int(sensor.full_spectrum),
            }
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def test_dht22(gpio_bcm, retries, retry_delay):
    gpio = _safe_int(gpio_bcm)
    retries = _safe_int(retries, 15)
    retry_delay = _safe_float(retry_delay, 0.5)

    try:
        import time
        import statistics
        import board
        import adafruit_dht

        pin_name = "D%s" % gpio
        if not hasattr(board, pin_name):
            return {
                "ok": False,
                "error": "GPIO pin not available on this board: BCM %s" % gpio
            }

        pin = getattr(board, pin_name)

        try:
            sensor = adafruit_dht.DHT22(pin, use_pulseio=False)
        except Exception as e:
            return {
                "ok": False,
                "error": "Could not initialize DHT22 on GPIO%s (BCM): %s" % (gpio, str(e))
            }

        # 🔧 Stabilisierung (wichtig!)
        time.sleep(3.0)

        temps = []
        hums = []
        last_error = None

        for _ in range(retries):
            try:
                t = sensor.temperature
                h = sensor.humidity

                if t is not None and h is not None:
                    t = float(t)
                    h = float(h)

                    # 🔥 typische Fake-Werte rausfiltern
                    if t in (0.0, 85.0):
                        continue

                    # Plausibilitätsbereich
                    if -40.0 <= t <= 85.0 and 0.0 <= h <= 100.0:
                        temps.append(t)
                        hums.append(h)
                    else:
                        last_error = "Received implausible values"

            except RuntimeError as e:
                # normale DHT-Fehler → ignorieren
                last_error = str(e)
            except Exception as e:
                last_error = str(e)
                break

            time.sleep(retry_delay)

        try:
            sensor.exit()
        except Exception:
            pass

        # 🔧 Fallback: schon 1 gültiger Wert reicht
        if len(temps) >= 1:
            temperature = statistics.median(temps)
            humidity = statistics.median(hums)

            return {
                "ok": True,
                "values": {
                    "temperature_c": round(temperature, 2),
                    "humidity_pct": round(humidity, 2)
                },
                "meta": {
                    "gpio_bcm": gpio,
                    "board_pin": pin_name,
                    "samples_ok": len(temps),
                    "retries": retries,
                    "retry_delay": retry_delay
                }
            }

        return {
            "ok": False,
            "error": last_error or "No valid DHT22 reading received",
            "meta": {
                "gpio_bcm": gpio,
                "board_pin": pin_name,
                "samples_ok": 0,
                "retries": retries,
                "retry_delay": retry_delay
            }
        }

    except ImportError as e:
        return {
            "ok": False,
            "error": "Required Python module missing: %s" % str(e)
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def test_ds18b20():
    try:
        base = "/sys/bus/w1/devices"
        sensors = sorted(glob.glob(os.path.join(base, "28-*")))
        if not sensors:
            return {"ok": False, "error": "No DS18B20 device found"}

        device_file = os.path.join(sensors[0], "w1_slave")
        if not os.path.isfile(device_file):
            return {"ok": False, "error": "w1_slave file not found"}

        with open(device_file, "r") as f:
            lines = f.read().splitlines()

        if len(lines) < 2 or "t=" not in lines[1]:
            return {"ok": False, "error": "Invalid DS18B20 response"}

        raw = lines[1].split("t=")[-1]
        temp_c = float(raw) / 1000.0

        return {
            "ok": True,
            "values": {
                "device": os.path.basename(sensors[0]),
                "temperature_c": round(temp_c, 2),
            }
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}