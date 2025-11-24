#!/usr/bin/env python3
"""
Gesamt-Testskript für alle Sensoren der AllSkyKamera:

- DHT22 / DHT11 an GPIO D6 (Pin 31)
- DS18B20 (1-Wire, /sys/bus/w1/devices/28-*)
- BME280 (I2C, 0x76)
- MLX90614 (I2C, 0x5A)
- TSL2591 (I2C)

Jeder Sensor wird getestet, Fehler werden abgefangen,
sodass das Skript immer komplett durchläuft.
"""

import time
import math
import os
import glob
import datetime
import statistics

# --------------------------------------------------------------------
# optionale Imports / Flags
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

# SMBus (für BME280 + MLX90614)
try:
    import smbus
    HAVE_SMBUS = True
except ImportError:
    HAVE_SMBUS = False

# TSL2591
try:
    import busio
    import adafruit_tsl2591
    HAVE_TSL = (board is not None)
except ImportError:
    HAVE_TSL = False

# globaler I2C-Bus (wird bei Bedarf initialisiert)
bus = None

# --------------------------------------------------------------------
# DHT22 / DHT11 (an D6)
# --------------------------------------------------------------------

DHT_GPIO = getattr(board, "D6", None) if board is not None else None


def _read_dht(sensor_class, retries=10, delay=0.3, t_min=-40.0, t_max=80.0):
    """Mehrfach DHT-Werte lesen, Ausreißer filtern, Median zurückgeben."""
    temps, hums = [], []

    try:
        dht = sensor_class(DHT_GPIO, use_pulseio=False)
    except Exception as e:
        print(f"  Konnte DHT-Sensor nicht initialisieren: {e}")
        return None, None

    # Sensor braucht etwas „Aufwachzeit“
    time.sleep(2.0)

    try:
        for _ in range(retries):
            try:
                t = dht.temperature
                h = dht.humidity
                if (
                    t is not None and h is not None
                    and t_min <= t <= t_max
                    and 0.0 <= h <= 100.0
                ):
                    temps.append(float(t))
                    hums.append(float(h))
            except RuntimeError:
                # typischer DHT-„Glitch“ – einfach ignorieren
                pass
            except Exception as e:
                print(f"  Einzelner DHT-Lesefehler: {e}")
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

    if not HAVE_DHT:
        msg = "DHT-Bibliothek (adafruit_dht/board) nicht installiert oder 'board' nicht verfügbar."
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "nicht verfügbar", "details": msg}
        print()
        return

    if DHT_GPIO is None:
        msg = "Kein GPIO für DHT konfiguriert (board.D6 nicht verfügbar)."
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "nicht verfügbar", "details": msg}
        print()
        return

    # Zuerst DHT22 versuchen
    try:
        print("Versuche zuerst DHT22 an D6 ...")
        t, h = _read_dht(adafruit_dht.DHT22, t_min=-40.0, t_max=80.0)
        if t is not None:
            msg = f"DHT22 OK: {t:.1f} °C, {h:.1f} % rF"
            print(msg)
            if summary is not None:
                summary["sensors"][sensor_key] = {"status": "OK", "details": msg}
            print()
            return
    except Exception as e:
        print(f"  Unerwarteter Fehler beim DHT22-Test: {e}")

    # Wenn DHT22 nichts liefert, DHT11 testen
    try:
        print("Kein gültiger DHT22, versuche DHT11 an D6 ...")
        t, h = _read_dht(adafruit_dht.DHT11, t_min=-20.0, t_max=60.0)
        if t is not None:
            msg = f"DHT11 OK: {t:.1f} °C, {h:.1f} % rF"
            print(msg)
            if summary is not None:
                summary["sensors"][sensor_key] = {"status": "OK", "details": msg}
        else:
            msg = "Kein funktionierender DHT22/DHT11 erkannt."
            print(msg)
            if summary is not None:
                summary["sensors"][sensor_key] = {"status": "nicht gefunden", "details": msg}
    except Exception as e:
        msg = f"  Unerwarteter Fehler beim DHT11-Test: {e}"
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "Fehler", "details": msg}
    print()


# --------------------------------------------------------------------
# DS18B20 (1-Wire)
# --------------------------------------------------------------------

def read_ds18b20():
    base_dir = '/sys/bus/w1/devices/'
    device_folders = glob.glob(base_dir + '28-*')
    if not device_folders:
        return None, "Kein DS18B20-Sensor gefunden (ist 1-Wire aktiviert?)"

    device_file = os.path.join(device_folders[0], 'w1_slave')

    try:
        with open(device_file, 'r') as f:
            lines = f.readlines()

        if not lines:
            return None, "Leere Antwort vom DS18B20"

        if lines[0].strip()[-3:] != 'YES':
            return None, "CRC-Fehler beim Lesen (erste Zeile endet nicht auf YES)"

        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
            temp_string = lines[1][equals_pos + 2:].strip()
            temperature_c = float(temp_string) / 1000.0
            return temperature_c, None
        else:
            return None, "Temperaturfeld 't=' nicht gefunden"
    except FileNotFoundError:
        return None, "DS18B20-Datei nicht gefunden (modprobe w1-gpio/w1-therm?)"
    except Exception as e:
        return None, f"Fehler: {e}"


def test_ds18b20(summary=None):
    sensor_key = "DS18B20"
    print("=== DS18B20 Test ===")
    temp, err = read_ds18b20()
    if err:
        print(err)
        if summary is not None:
            status = "Fehler"
            if "Kein DS18B20" in err or "nicht gefunden" in err:
                status = "nicht gefunden"
            summary["sensors"][sensor_key] = {"status": status, "details": err}
    else:
        msg = f"Temperatur: {temp:.2f} °C"
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "OK", "details": msg}
    print()


# --------------------------------------------------------------------
# BME280 (I2C, 0x76)
# --------------------------------------------------------------------

DEVICE_BME = 0x76

from ctypes import c_short  # für Vorzeichen-Konvertierung


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
    """Direkt aus deinem BME280-Testskript übernommen, leicht bereinigt."""
    global bus

    REG_DATA = 0xF7
    REG_CONTROL = 0xF4
    REG_CONFIG = 0xF5
    REG_CONTROL_HUM = 0xF2
    OVERSAMPLE_TEMP = 2
    OVERSAMPLE_PRES = 2
    MODE = 1
    OVERSAMPLE_HUM = 2

    # Humidity Oversampling
    bus.write_byte_data(addr, REG_CONTROL_HUM, OVERSAMPLE_HUM)
    # Temperatur + Druck Oversampling + Mode
    control = OVERSAMPLE_TEMP << 5 | OVERSAMPLE_PRES << 2 | MODE
    bus.write_byte_data(addr, REG_CONTROL, control)

    # Kalibrierungsdaten
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
    time.sleep(wait_time / 1000)

    data = bus.read_i2c_block_data(addr, REG_DATA, 8)
    pres_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
    temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
    hum_raw = (data[6] << 8) | data[7]

    # Temperatur
    var1 = ((((temp_raw >> 3) - (dig_T1 << 1)) * (dig_T2)) >> 11)
    var2 = (
        (((((temp_raw >> 4) - (dig_T1)) * ((temp_raw >> 4) - (dig_T1))) >> 12) * (dig_T3))
        >> 14
    )
    t_fine = var1 + var2
    temperature = float(((t_fine * 5) + 128) >> 8)

    # Druck
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

    # Luftfeuchte
    humidity = t_fine - 76800.0
    humidity = (
        (hum_raw - (dig_H4 * 64.0 + dig_H5 / 16384.0 * humidity))
        * (dig_H2 / 65536.0 * (1.0 + dig_H6 / 67108864.0 * humidity
                               * (1.0 + dig_H3 / 67108864.0 * humidity)))
    )
    humidity = humidity * (1.0 - dig_H1 * humidity / 524288.0)
    humidity = max(0, min(humidity, 100))

    return temperature / 100.0, pressure / 100.0, humidity


def taupunkt(temp, hum):
    a = 17.62
    b = 243.12
    alpha = ((a * temp) / (b + temp)) + math.log(hum / 100.0)
    return (b * alpha) / (a - alpha)


def test_bme280(summary=None):
    sensor_key = "BME280"
    print("=== BME280 Test ===")
    if not HAVE_SMBUS:
        msg = "smbus-Modul nicht installiert – BME280 kann nicht gelesen werden."
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "nicht verfügbar", "details": msg}
        print()
        return

    global bus
    try:
        if bus is None:
            bus = smbus.SMBus(1)
    except Exception as e:
        msg = f"I2C-Bus konnte nicht geöffnet werden (SMBus(1)): {e}\nIst I2C aktiviert? (raspi-config)"
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "Fehler", "details": msg}
        print()
        return

    try:
        temperature, pressure, humidity = readBME280All()
    except OSError as e:
        msg = f"Kein BME280 an Adresse 0x76 erreichbar? I2C-Fehler: {e}"
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "nicht gefunden", "details": msg}
        print()
        return
    except Exception as e:
        msg = f"Fehler beim Lesen des BME280: {e}"
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "Fehler", "details": msg}
        print()
        return

    td = taupunkt(temperature, humidity)
    msg_lines = [
        f"Temperatur : {temperature:.2f} °C",
        f"Druck      : {pressure:.2f} hPa",
        f"Feuchte    : {humidity:.2f} %",
        f"Taupunkt   : {td:.2f} °C",
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
    if not HAVE_SMBUS:
        msg = "smbus-Modul nicht installiert – MLX90614 kann nicht gelesen werden."
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "nicht verfügbar", "details": msg}
        print()
        return

    global bus
    try:
        if bus is None:
            bus = smbus.SMBus(1)
    except Exception as e:
        msg = f"I2C-Bus konnte nicht geöffnet werden (SMBus(1)): {e}\nIst I2C aktiviert? (raspi-config)"
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "Fehler", "details": msg}
        print()
        return

    REG_TA = 0x06
    REG_TOBJ1 = 0x07

    try:
        ta = read_mlx_temperature(DEVICE_MLX, REG_TA, check_pec=False)
        tobj1 = read_mlx_temperature(DEVICE_MLX, REG_TOBJ1, check_pec=False)
        msg1 = f"Umgebung: {ta:.2f} °C"
        msg2 = f"Objekt  : {tobj1:.2f} °C"
        print(msg1)
        print(msg2)
        if summary is not None:
            summary["sensors"][sensor_key] = {
                "status": "OK",
                "details": f"{msg1}; {msg2}",
            }
    except OSError as e:
        msg = f"I2C-Fehler (kein MLX90614 an 0x5A?): {e}"
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "nicht gefunden", "details": msg}
    except ValueError as e:
        msg = f"Datenfehler (PEC/Format): {e}"
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "Fehler", "details": msg}
    except Exception as e:
        msg = f"Unerwarteter Fehler beim MLX90614: {e}"
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "Fehler", "details": msg}
    print()


# --------------------------------------------------------------------
# TSL2591 (I2C)
# --------------------------------------------------------------------

def test_tsl2591(summary=None):
    sensor_key = "TSL2591"
    print("=== TSL2591 Test ===")
    if not HAVE_TSL:
        msg = "TSL2591-Bibliotheken (busio/adafruit_tsl2591) oder 'board' nicht installiert."
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "nicht verfügbar", "details": msg}
        print()
        return

    if board is None:
        msg = "'board'-Modul nicht verfügbar – kann I2C-Pins nicht bestimmen."
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "nicht verfügbar", "details": msg}
        print()
        return

    try:
        i2c = busio.I2C(board.SCL, board.SDA)
    except Exception as e:
        msg = f"I2C konnte nicht initialisiert werden (busio.I2C): {e}\nIst I2C aktiviert? (raspi-config)"
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "Fehler", "details": msg}
        print()
        return

    try:
        sensor = adafruit_tsl2591.TSL2591(i2c)

        lux = sensor.lux or 0.0001
        visible = sensor.visible or 0.0001
        infrared = sensor.infrared or 0.0001
        full = sensor.full_spectrum or 0.0001

        skybright = 22.0 - 2.5 * math.log10(lux)
        skybright2 = 22.0 - 2.5 * math.log10(visible)
        if skybright2 < 6.0:
            skybright2 = 0.0001

        msg_lines = [
            f"Lux-Wert      : {lux:.2f} lx",
            f"Sichtbar      : {visible}",
            f"Infrarot      : {infrared}",
            f"Vollspektrum  : {full}",
            f"Himmelshelligkeit (mag/arcsec²)     : {skybright:.2f}",
            f"Himmelshelligkeit Vis (mag/arcsec²): {skybright2:.2f}",
        ]
        for line in msg_lines:
            print(line)
        if summary is not None:
            summary["sensors"][sensor_key] = {
                "status": "OK",
                "details": "; ".join(msg_lines),
            }
    except OSError as e:
        msg = f"I2C-Fehler (kein TSL2591 am Bus?): {e}"
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "nicht gefunden", "details": msg}
    except Exception as e:
        msg = f"Unerwarteter Fehler beim TSL2591: {e}"
        print(msg)
        if summary is not None:
            summary["sensors"][sensor_key] = {"status": "Fehler", "details": msg}
    print()


# --------------------------------------------------------------------
# Bus-Checks: I2C und 1-Wire
# --------------------------------------------------------------------

def test_i2c_bus(summary=None):
    bus_key = "i2c"
    print("=== I2C-Bus Test ===")
    # Check /dev/i2c-1
    dev_path = "/dev/i2c-1"
    if not os.path.exists(dev_path):
        msg = f"{dev_path} existiert nicht. I2C vermutlich nicht aktiviert."
        print(msg)
        if summary is not None:
            summary["buses"][bus_key] = {"status": "nicht verfügbar", "details": msg}
        print()
        return

    if not HAVE_SMBUS:
        msg = "smbus-Modul nicht installiert. I2C kann von Python aus nicht genutzt werden."
        print(msg)
        if summary is not None:
            summary["buses"][bus_key] = {"status": "nicht verfügbar", "details": msg}
        print()
        return

    try:
        tmp = smbus.SMBus(1)
        # Wenn wir hier sind, ist der Bus ansprechbar
        tmp.close()
        msg = "/dev/i2c-1 vorhanden, smbus.SMBus(1) konnte geöffnet werden."
        print(msg)
        if summary is not None:
            summary["buses"][bus_key] = {"status": "OK", "details": msg}
    except Exception as e:
        msg = f"/dev/i2c-1 vorhanden, aber Öffnen mit smbus.SMBus(1) fehlgeschlagen: {e}"
        print(msg)
        if summary is not None:
            summary["buses"][bus_key] = {"status": "Fehler", "details": msg}
    print()


def test_onewire_bus(summary=None):
    bus_key = "onewire"
    print("=== 1-Wire-Bus Test ===")
    base_dir = "/sys/bus/w1/devices"
    if not os.path.isdir(base_dir):
        msg = f"{base_dir} existiert nicht. 1-Wire vermutlich nicht aktiviert."
        print(msg)
        if summary is not None:
            summary["buses"][bus_key] = {"status": "nicht verfügbar", "details": msg}
        print()
        return

    try:
        entries = os.listdir(base_dir)
    except Exception as e:
        msg = f"Verzeichnis {base_dir} konnte nicht gelesen werden: {e}"
        print(msg)
        if summary is not None:
            summary["buses"][bus_key] = {"status": "Fehler", "details": msg}
        print()
        return

    masters = [e for e in entries if e.startswith("w1_bus_master")]
    devices = [e for e in entries if e.startswith("28-")]

    if masters:
        msg = f"1-Wire Master gefunden: {', '.join(masters)}"
        print(msg)
        if devices:
            msg2 = f"Angeschlossene 1-Wire-Devices: {', '.join(devices)}"
            print(msg2)
            combined = msg + "; " + msg2
        else:
            msg2 = "Kein DS18B20 (28-*) gefunden, aber Bus ist aktiv."
            print(msg2)
            combined = msg + "; " + msg2
        if summary is not None:
            summary["buses"][bus_key] = {"status": "OK", "details": combined}
    else:
        msg = "Kein w1_bus_master* gefunden – 1-Wire scheint nicht aktiv zu sein."
        print(msg)
        if summary is not None:
            summary["buses"][bus_key] = {"status": "nicht gefunden", "details": msg}
    print()


# --------------------------------------------------------------------
# Zusammenfassung
# --------------------------------------------------------------------

def print_summary(summary):
    print("===================================================")
    print("  Zusammenfassung")
    print("===================================================")

    buses = summary.get("buses", {})
    sensors = summary.get("sensors", {})

    print("\nBus-Schnittstellen:")
    for key, label in [("i2c", "I2C"), ("onewire", "1-Wire")]:
        info = buses.get(key)
        if info is None:
            print(f"- {label}: nicht getestet")
        else:
            print(f"- {label}: {info.get('status', 'unbekannt')} – {info.get('details', '')}")

    print("\nSensoren:")
    sensor_labels = [
        ("DHT", "DHT22/DHT11"),
        ("DS18B20", "DS18B20"),
        ("BME280", "BME280"),
        ("MLX90614", "MLX90614"),
        ("TSL2591", "TSL2591"),
    ]
    for key, label in sensor_labels:
        info = sensors.get(key)
        if info is None:
            print(f"- {label}: nicht getestet")
        else:
            print(f"- {label}: {info.get('status', 'unbekannt')} – {info.get('details', '')}")

    # kleine Gesamtübersicht
    ok_sensors = [k for k, v in sensors.items() if v.get("status") == "OK"]
    problem_sensors = [k for k, v in sensors.items() if v.get("status") != "OK"]

    print("\nGesamt:")
    print(f"- OK-Sensoren       : {len(ok_sensors)} ({', '.join(ok_sensors) or '-'})")
    print(f"- Problem-Sensoren  : {len(problem_sensors)} ({', '.join(problem_sensors) or '-'})")


# --------------------------------------------------------------------
# Main
# --------------------------------------------------------------------

def main():
    print("===================================================")
    print("  AllSkyKamera – Gesamttest aller Sensoren")
    print("  Zeit: ", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("===================================================\n")

    summary = {"buses": {}, "sensors": {}}

    # Bus-Checks zuerst
    try:
        test_i2c_bus(summary)
    except Exception as e:
        print(f"[FEHLER] test_i2c_bus ist unerwartet abgestürzt: {e}\n")
    try:
        test_onewire_bus(summary)
    except Exception as e:
        print(f"[FEHLER] test_onewire_bus ist unerwartet abgestürzt: {e}\n")

    # Jede Testfunktion wird einzeln abgesichert, damit nichts das Skript killt
    for fn in (test_dht, test_ds18b20, test_bme280, test_mlx90614, test_tsl2591):
        try:
            fn(summary)
        except Exception as e:
            print(f"[FEHLER] {fn.__name__} ist unerwartet abgestürzt: {e}\n")

    print_summary(summary)
    print("\nFertig. Alle verfügbaren Sensoren wurden getestet.")


if __name__ == "__main__":
    main()
