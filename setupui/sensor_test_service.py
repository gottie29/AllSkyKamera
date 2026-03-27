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


def test_tsl2591(address, gain="med", exposure_ms=200, samples=3, interval=0.8,
                 auto_range_enabled=True, auto_verbose=False, sqm_const=22.0):
    addr = _safe_int(address)
    samples = max(1, _safe_int(samples, 3))
    interval = max(0.0, _safe_float(interval, 0.8))
    exposure_ms = _safe_int(exposure_ms, 200)
    sqm_const = _safe_float(sqm_const, 22.0)

    try:
        import math
        import time
        import statistics
        import board
        import busio
        import adafruit_tsl2591

        def safe_value(x, fallback=0.0001):
            try:
                if x is None:
                    return fallback
                x = float(x)
                if x <= 0:
                    return fallback
                return x
            except Exception:
                return fallback

        def set_gain_and_exposure(sensor, gain_str, exp_ms):
            gain_map = {
                "low": adafruit_tsl2591.GAIN_LOW,
                "med": adafruit_tsl2591.GAIN_MED,
                "high": adafruit_tsl2591.GAIN_HIGH,
                "max": adafruit_tsl2591.GAIN_MAX,
            }
            it_map = {
                100: adafruit_tsl2591.INTEGRATIONTIME_100MS,
                200: adafruit_tsl2591.INTEGRATIONTIME_200MS,
                300: adafruit_tsl2591.INTEGRATIONTIME_300MS,
                400: adafruit_tsl2591.INTEGRATIONTIME_400MS,
                500: adafruit_tsl2591.INTEGRATIONTIME_500MS,
                600: adafruit_tsl2591.INTEGRATIONTIME_600MS,
            }

            if gain_str not in gain_map:
                gain_str = "med"
            if exp_ms not in it_map:
                exp_ms = 200

            sensor.gain = gain_map[gain_str]
            sensor.integration_time = it_map[exp_ms]

        def read_raw_counts(sensor):
            try:
                raw = sensor.raw_luminosity
                if isinstance(raw, tuple) and len(raw) >= 2:
                    return int(raw[0]), int(raw[1])
            except Exception:
                pass
            return None, None

        def settle_for_integration(exp_ms):
            time.sleep(exp_ms / 1000.0 + 0.05)

        def compute_sqm_from_ch0(ch0, const):
            if ch0 is None or ch0 <= 0:
                return None
            return const - 2.5 * math.log10(float(ch0))

        def auto_range(sensor, verbose=False):
            gain_factors = {"low": 1, "med": 25, "high": 428, "max": 9876}
            gains = ["low", "med", "high", "max"]
            exposures = [100, 200, 300, 400, 500, 600]

            combos = []
            for g in gains:
                for e in exposures:
                    combos.append((gain_factors[g] * e, g, e))
            combos.sort(key=lambda x: x[0])

            TARGET_LOW = 2000
            TARGET_HIGH = 45000
            SAT_THRESHOLD = 65000

            best = None
            best_score = None
            scan = []

            for _, g, e in combos:
                try:
                    set_gain_and_exposure(sensor, g, e)
                except Exception as ex:
                    if verbose:
                        scan.append({
                            "gain": g,
                            "exposure_ms": e,
                            "error": "set failed: %s" % str(ex)
                        })
                    continue

                settle_for_integration(e)
                ch0, ch1 = read_raw_counts(sensor)

                if ch0 is None:
                    try:
                        lux = safe_value(sensor.lux, fallback=0.0)
                    except Exception:
                        lux = 0.0

                    score = lux
                    if verbose:
                        scan.append({
                            "gain": g,
                            "exposure_ms": e,
                            "lux": round(lux, 3),
                            "note": "no raw"
                        })

                    if best_score is None or score > best_score:
                        best_score = score
                        best = (g, e)
                    continue

                saturated = (ch0 >= SAT_THRESHOLD) or (ch1 >= SAT_THRESHOLD)
                too_dark = (ch0 < TARGET_LOW)
                in_window = (TARGET_LOW <= ch0 <= TARGET_HIGH) and not saturated

                if verbose:
                    scan.append({
                        "gain": g,
                        "exposure_ms": e,
                        "ch0": ch0,
                        "ch1": ch1,
                        "saturated": saturated,
                        "too_dark": too_dark,
                        "ok_window": in_window,
                    })

                if in_window:
                    return (g, e, scan)

                if saturated:
                    score = -10000000 - ch0
                else:
                    if ch0 <= TARGET_HIGH:
                        score = ch0
                    else:
                        score = TARGET_HIGH - (ch0 - TARGET_HIGH)

                if best_score is None or score > best_score:
                    best_score = score
                    best = (g, e)

            if best is None:
                best = ("med", 200)

            return (best[0], best[1], scan)

        try:
            i2c = busio.I2C(board.SCL, board.SDA)
        except Exception as e:
            return {
                "ok": False,
                "error": "Could not open I2C interface: %s" % str(e)
            }

        try:
            sensor = adafruit_tsl2591.TSL2591(i2c, address=addr)
        except Exception as e:
            return {
                "ok": False,
                "error": "Could not initialize TSL2591 at 0x%02X: %s" % (addr, str(e))
            }

        if auto_range_enabled:
            selected_gain, selected_exp, auto_scan = auto_range(sensor, verbose=auto_verbose)
        else:
            selected_gain = gain
            selected_exp = exposure_ms
            auto_scan = []

        try:
            set_gain_and_exposure(sensor, selected_gain, selected_exp)
            settle_for_integration(selected_exp)
        except Exception as e:
            return {
                "ok": False,
                "error": "Could not apply TSL2591 settings: %s" % str(e)
            }

        lux_values = []
        visible_values = []
        infrared_values = []
        full_values = []
        ch0_values = []
        ch1_values = []
        sqm_values = []
        sample_rows = []
        last_error = None

        for idx in range(samples):
            try:
                lux = safe_value(sensor.lux)
                visible = safe_value(sensor.visible)
                infrared = safe_value(sensor.infrared)
                full = safe_value(sensor.full_spectrum)
                ch0, ch1 = read_raw_counts(sensor)

                lux_values.append(float(lux))
                visible_values.append(float(visible))
                infrared_values.append(float(infrared))
                full_values.append(float(full))

                row = {
                    "sample": idx + 1,
                    "lux": round(float(lux), 3),
                    "visible": round(float(visible), 3),
                    "infrared": round(float(infrared), 3),
                    "full_spectrum": round(float(full), 3),
                }

                if ch0 is not None:
                    sqm = compute_sqm_from_ch0(ch0, sqm_const)
                    sat = (ch0 >= 65000) or (ch1 >= 65000)

                    ch0_values.append(ch0)
                    ch1_values.append(ch1)
                    if sqm is not None:
                        sqm_values.append(sqm)

                    row["raw_ch0"] = ch0
                    row["raw_ch1"] = ch1
                    row["saturated"] = sat
                    row["sqm_ch0"] = round(sqm, 2) if sqm is not None else None

                sample_rows.append(row)

            except Exception as e:
                last_error = str(e)

            if idx < (samples - 1):
                time.sleep(interval)

        if not sample_rows:
            return {
                "ok": False,
                "error": last_error or "No valid TSL2591 reading received",
                "meta": {
                    "address": "0x%02X" % addr,
                    "selected_gain": selected_gain,
                    "selected_exposure_ms": selected_exp,
                }
            }

        result = {
            "ok": True,
            "values": {
                "lux": round(statistics.median(lux_values), 3) if lux_values else None,
                "visible": round(statistics.median(visible_values), 3) if visible_values else None,
                "infrared": round(statistics.median(infrared_values), 3) if infrared_values else None,
                "full_spectrum": round(statistics.median(full_values), 3) if full_values else None,
                "raw_ch0": int(statistics.median(ch0_values)) if ch0_values else None,
                "raw_ch1": int(statistics.median(ch1_values)) if ch1_values else None,
                "sqm_ch0": round(statistics.median(sqm_values), 2) if sqm_values else None,
            },
            "meta": {
                "address": "0x%02X" % addr,
                "selected_gain": selected_gain,
                "selected_exposure_ms": selected_exp,
                "samples_ok": len(sample_rows),
                "samples_requested": samples,
                "interval_s": interval,
                "auto_range": bool(auto_range_enabled),
                "sqm_const": sqm_const,
            },
            "samples": sample_rows,
        }

        if auto_verbose and auto_scan:
            result["meta"]["auto_scan"] = auto_scan

        if last_error:
            result["meta"]["last_error"] = last_error

        return result

    except ImportError as e:
        return {
            "ok": False,
            "error": "Required Python module missing: %s" % str(e)
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

def test_dht11(gpio_bcm, retries, retry_delay):
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
            sensor = adafruit_dht.DHT11(pin, use_pulseio=False)
        except Exception as e:
            return {
                "ok": False,
                "error": "Could not initialize DHT11 on GPIO%s (BCM): %s" % (gpio, str(e))
            }

        time.sleep(2.0)

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

                    if -20.0 <= t <= 60.0 and 0.0 <= h <= 100.0:
                        temps.append(t)
                        hums.append(h)
                    else:
                        last_error = "Received implausible values"

            except RuntimeError as e:
                last_error = str(e)
            except Exception as e:
                last_error = str(e)
                break

            time.sleep(retry_delay)

        try:
            sensor.exit()
        except Exception:
            pass

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
            "error": last_error or "No valid DHT11 reading received",
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
    
def test_mlx90614(address):
    addr = _safe_int(address, 0x5A)

    try:
        import time

        try:
            import smbus
        except ImportError:
            return {
                "ok": False,
                "error": "Python smbus library is not installed. Install: sudo apt-get install python3-smbus i2c-tools"
            }

        BUS_NUMBER = 1
        REG_TA = 0x06
        REG_TOBJ1 = 0x07

        def raw_to_celsius(raw):
            return (raw * 0.02) - 273.15

        def read_raw_pec(bus, sensor_addr, reg):
            data = bus.read_i2c_block_data(sensor_addr, reg, 3)
            lsb, msb = data[0], data[1]
            raw = (msb << 8) | lsb
            return raw

        def read_temperature(bus, sensor_addr, reg):
            raw = read_raw_pec(bus, sensor_addr, reg)
            t = raw_to_celsius(raw)

            # Fallback: byte swap if implausible
            if not (-70.0 <= t <= 380.0):
                swapped = ((raw & 0xFF) << 8) | (raw >> 8)
                t_swapped = raw_to_celsius(swapped)
                if -70.0 <= t_swapped <= 380.0:
                    t = t_swapped

            return round(t, 2)

        try:
            bus = smbus.SMBus(BUS_NUMBER)
        except Exception as e:
            return {
                "ok": False,
                "error": "Could not open I2C bus %s: %s" % (BUS_NUMBER, str(e))
            }

        ambient_values = []
        object_values = []
        last_error = None
        samples = 3

        try:
            for _ in range(samples):
                try:
                    ta = read_temperature(bus, addr, REG_TA)
                    tobj1 = read_temperature(bus, addr, REG_TOBJ1)

                    ambient_values.append(float(ta))
                    object_values.append(float(tobj1))

                except OSError as e:
                    last_error = "I2C error while reading sensor: %s" % str(e)
                    break
                except ValueError as e:
                    last_error = "Data error: %s" % str(e)
                    break

                time.sleep(0.5)

        finally:
            try:
                bus.close()
            except Exception:
                pass

        if not ambient_values or not object_values:
            return {
                "ok": False,
                "error": last_error or ("No valid MLX90614 reading received at 0x%02X" % addr)
            }

        ambient_avg = round(sum(ambient_values) / len(ambient_values), 2)
        object_avg = round(sum(object_values) / len(object_values), 2)
        delta_avg = round(object_avg - ambient_avg, 2)

        return {
            "ok": True,
            "values": {
                "address": "0x%02X" % addr,
                "ambient_temperature_c": ambient_avg,
                "object_temperature_c": object_avg,
                "delta_c": delta_avg
            },
            "meta": {
                "samples_ok": len(ambient_values),
                "bus_number": BUS_NUMBER
            }
        }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e)
        }
        
def test_htu21(address):
    addr = _safe_int(address, 0x40)

    try:
        import time
        import statistics
        import board
        import busio

        try:
            import adafruit_htu21d
        except ImportError:
            return {
                "ok": False,
                "error": "Required Python module missing: adafruit-circuitpython-htu21d"
            }

        i2c = busio.I2C(board.SCL, board.SDA)

        try:
            sensor = adafruit_htu21d.HTU21D(i2c, address=addr)
        except TypeError:
            sensor = adafruit_htu21d.HTU21D(i2c)

        temp_values = []
        hum_values = []
        last_error = None

        for _ in range(3):
            try:
                t = float(sensor.temperature)
                h = float(sensor.relative_humidity)

                if -40.0 <= t <= 125.0 and 0.0 <= h <= 100.0:
                    temp_values.append(t)
                    hum_values.append(h)
                else:
                    last_error = "Received implausible values"
            except Exception as e:
                last_error = str(e)

            time.sleep(0.5)

        if not temp_values or not hum_values:
            return {
                "ok": False,
                "error": last_error or ("No valid HTU21 reading received at 0x%02X" % addr)
            }

        return {
            "ok": True,
            "values": {
                "address": "0x%02X" % addr,
                "temperature_c": round(statistics.median(temp_values), 2),
                "humidity_pct": round(statistics.median(hum_values), 2),
            },
            "meta": {
                "samples_ok": len(temp_values)
            }
        }

    except ImportError as e:
        return {"ok": False, "error": "Required Python module missing: %s" % str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    
def test_sht3x(address):
    addr = _safe_int(address, 0x44)

    try:
        import time
        import statistics
        import board
        import busio

        try:
            import adafruit_sht31d
        except ImportError:
            return {
                "ok": False,
                "error": "Required Python module missing: adafruit-circuitpython-sht31d"
            }

        i2c = busio.I2C(board.SCL, board.SDA)
        sensor = adafruit_sht31d.SHT31D(i2c, address=addr)

        temp_values = []
        hum_values = []
        last_error = None

        for _ in range(3):
            try:
                t = float(sensor.temperature)
                h = float(sensor.relative_humidity)

                if -40.0 <= t <= 125.0 and 0.0 <= h <= 100.0:
                    temp_values.append(t)
                    hum_values.append(h)
                else:
                    last_error = "Received implausible values"
            except Exception as e:
                last_error = str(e)

            time.sleep(0.5)

        if not temp_values or not hum_values:
            return {
                "ok": False,
                "error": last_error or ("No valid SHT3X reading received at 0x%02X" % addr)
            }

        return {
            "ok": True,
            "values": {
                "address": "0x%02X" % addr,
                "temperature_c": round(statistics.median(temp_values), 2),
                "humidity_pct": round(statistics.median(hum_values), 2),
            },
            "meta": {
                "samples_ok": len(temp_values)
            }
        }

    except ImportError as e:
        return {"ok": False, "error": "Required Python module missing: %s" % str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)} 