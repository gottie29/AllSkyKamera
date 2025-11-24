#!/usr/bin/env python3
# Datei: humidity_relay.py
import os
import sys
import time
import math
import datetime
from ctypes import c_short, c_byte, c_ubyte

import smbus
import RPi.GPIO as GPIO
GPIO.setwarnings(False)


# ==========================
# Konfiguration
# ==========================

# BME280
DEVICE = 0x76        # I2C-Adresse (ggf. 0x77)
bus = smbus.SMBus(1) # I2C-Bus (1 für neuere Raspberry Pis)

# Relais
RELAIS_PIN = 26      # GPIO-Nummer (BCM)
STATE_DIR  = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(STATE_DIR, f"relay_{RELAIS_PIN}.state")  # Inhalt: "ON" oder "OFF"

# Feuchte-Schwellen (Hysterese)
HUM_ON  = 60.0       # Relais AN, wenn Luftfeuchtigkeit > HUM_ON
HUM_OFF = 55.0       # Relais AUS, wenn Luftfeuchtigkeit < HUM_OFF


# ==========================
# BME280-Hilfsfunktionen
# ==========================

def getShort(data, index):
    return c_short((data[index+1] << 8) + data[index]).value

def getUShort(data, index):
    return (data[index+1] << 8) + data[index]

def getChar(data,index):
    result = data[index]
    if result > 127:
        result -= 256
    return result

def getUChar(data,index):
    return data[index] & 0xFF

def readBME280ID(addr=DEVICE):
    REG_ID = 0xD0
    (chip_id, chip_version) = bus.read_i2c_block_data(addr, REG_ID, 2)
    return (chip_id, chip_version)

def readBME280All(addr=DEVICE):
    REG_DATA        = 0xF7
    REG_CONTROL     = 0xF4
    REG_CONFIG      = 0xF5
    REG_CONTROL_HUM = 0xF2

    OVERSAMPLE_TEMP = 2
    OVERSAMPLE_PRES = 2
    MODE            = 1
    OVERSAMPLE_HUM  = 2

    # Oversampling setzen
    bus.write_byte_data(addr, REG_CONTROL_HUM, OVERSAMPLE_HUM)
    control = OVERSAMPLE_TEMP << 5 | OVERSAMPLE_PRES << 2 | MODE
    bus.write_byte_data(addr, REG_CONTROL, control)

    # Kalibrierdaten lesen
    cal1 = bus.read_i2c_block_data(addr, 0x88, 24)
    cal2 = bus.read_i2c_block_data(addr, 0xA1, 1)
    cal3 = bus.read_i2c_block_data(addr, 0xE1, 7)

    dig_T1 = getUShort(cal1, 0)
    dig_T2 = getShort(cal1, 2)
    dig_T3 = getShort(cal1, 4)

    dig_P1 = getUShort(cal1, 6)
    dig_P2 = getShort(cal1, 8)
    dig_P3 = getShort(cal1, 10)
    dig_P4 = getShort(cal1, 12)
    dig_P5 = getShort(cal1, 14)
    dig_P6 = getShort(cal1, 16)
    dig_P7 = getShort(cal1, 18)
    dig_P8 = getShort(cal1, 20)
    dig_P9 = getShort(cal1, 22)

    dig_H1 = getUChar(cal2, 0)
    dig_H2 = getShort(cal3, 0)
    dig_H3 = getUChar(cal3, 2)

    dig_H4 = getChar(cal3, 3)
    dig_H4 = (dig_H4 << 24) >> 20
    dig_H4 |= getChar(cal3, 4) & 0x0F

    dig_H5 = getChar(cal3, 5)
    dig_H5 = (dig_H5 << 24) >> 20
    dig_H5 |= getUChar(cal3, 4) >> 4 & 0x0F

    dig_H6 = getChar(cal3, 6)

    # Messzeit warten
    wait_time = 1.25 + (2.3 * OVERSAMPLE_TEMP) + ((2.3 * OVERSAMPLE_PRES) + 0.575) + ((2.3 * OVERSAMPLE_HUM)+0.575)
    time.sleep(wait_time / 1000)

    # Messdaten lesen
    data = bus.read_i2c_block_data(addr, REG_DATA, 8)
    pres_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
    temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
    hum_raw  = (data[6] << 8) | data[7]

    # Temperatur
    var1 = ((((temp_raw >> 3) - (dig_T1 << 1))) * (dig_T2)) >> 11
    var2 = (((((temp_raw >> 4) - (dig_T1)) * ((temp_raw >> 4) - (dig_T1))) >> 12) * (dig_T3)) >> 14
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

    # Luftfeuchtigkeit
    humidity = t_fine - 76800.0
    humidity = (hum_raw - (dig_H4 * 64.0 + dig_H5 / 16384.0 * humidity)) * \
               (dig_H2 / 65536.0 * (1.0 + dig_H6 / 67108864.0 * humidity * (1.0 + dig_H3 / 67108864.0 * humidity)))
    humidity = humidity * (1.0 - dig_H1 * humidity / 524288.0)
    humidity = max(0, min(humidity, 100))

    return temperature / 100.0, pressure / 100.0, humidity


def berechne_taupunkt(temp, hum):
    # Magnus-Formel
    a = 17.62
    b = 243.12
    alpha = ((a * temp) / (b + temp)) + math.log(hum / 100.0)
    taupunkt = (b * alpha) / (a - alpha)
    return round(taupunkt, 2)


# ==========================
# Relais-Hilfsfunktionen
# ==========================

def ensure_state_dir():
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
    except PermissionError:
        print(f"Keine Schreibrechte für {STATE_DIR}. Bitte Rechte prüfen.", file=sys.stderr)
        sys.exit(1)

def read_state():
    if not os.path.isfile(STATE_FILE):
        return "OFF"
    try:
        with open(STATE_FILE, "r") as f:
            val = f.read().strip().upper()
            return "ON" if val == "ON" else "OFF"
    except Exception:
        return "OFF"

def write_state(state):
    with open(STATE_FILE, "w") as f:
        f.write("ON" if state == "ON" else "OFF")

def gpio_level_for(state):
    # High-aktiv: ON -> HIGH (zieht an), OFF -> LOW
    return GPIO.HIGH if state == "ON" else GPIO.LOW

def apply_state(state):
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RELAIS_PIN, GPIO.OUT, initial=gpio_level_for(state))
    # Kein GPIO.cleanup(), damit der Pegel erhalten bleibt


# ==========================
# Hauptlogik
# ==========================

def main():
    ensure_state_dir()

    # BME280 auslesen
    try:
        (chip_id, chip_version) = readBME280ID()
        temperature, pressure, humidity = readBME280All()
        taupunkt = berechne_taupunkt(temperature, humidity)
    except Exception as e:
        print(f"Fehler beim Lesen des BME280: {e}")
        return

    print(f"🌡️ Temperatur : {temperature:.2f} °C")
    print(f"🧭 Druck      : {pressure:.2f} hPa")
    print(f"💧 Feuchte    : {humidity:.2f} %")
    print(f"❄️ Taupunkt   : {taupunkt:.2f} °C")

    # Relaiszustand lesen
    last = read_state()
    print(f"Aktueller Relaiszustand: {last}")

    new = last

    # Hysterese-Logik
    if humidity > HUM_ON and last != "ON":
        new = "ON"
        print(f"Feuchte {humidity:.2f}% > {HUM_ON:.2f}% → Relais EIN")
    elif humidity < HUM_OFF and last != "OFF":
        new = "OFF"
        print(f"Feuchte {humidity:.2f}% < {HUM_OFF:.2f}% → Relais AUS")
    else:
        print("Keine Änderung am Relais (Hysterese-Bereich).")

    # Relais setzen & Zustand speichern
    apply_state(new)
    if new != last:
        write_state(new)
        print(f"Relais: {last} -> {new}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
