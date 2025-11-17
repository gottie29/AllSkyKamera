#!/usr/bin/env python3
# Datei: humidity_control.py
import subprocess
import smbus2
import bme280

# === Konfiguration ===
I2C_PORT = 1
I2C_ADDRESS = 0x76       # ggf. 0x77 – je nach Sensor

HUM_ON  = 60.0           # Relais AN, wenn Feuchte > HUM_ON
HUM_OFF = 55.0           # Relais AUS, wenn Feuchte < HUM_OFF

# Pfad zum Relais-Skript
RELAY_SCRIPT = "/home/pi/relay.py"   # anpassen falls woanders liegt


def read_humidity():
    """Liest die Luftfeuchtigkeit vom BME280 aus."""
    bus = smbus2.SMBus(I2C_PORT)
    calibration_params = bme280.load_calibration_params(bus, I2C_ADDRESS)
    data = bme280.sample(bus, I2C_ADDRESS, calibration_params)
    return data.humidity   # in Prozent (%)


def get_relay_state():
    """Fragt den aktuellen Relaiszustand ab (ON/OFF)."""
    result = subprocess.run(
        ["python3", RELAY_SCRIPT, "status"],
        capture_output=True,
        text=True
    )
    # Status ist die erste Zeile, also "ON" oder "OFF"
    for line in result.stdout.splitlines():
        if line.strip() in ("ON", "OFF"):
            return line.strip()
    return "OFF"


def relay_on():
    subprocess.run(["python3", RELAY_SCRIPT, "on"])


def relay_off():
    subprocess.run(["python3", RELAY_SCRIPT, "off"])


def main():
    humidity = read_humidity()
    print(f"Aktuelle Luftfeuchtigkeit: {humidity:.1f}%")

    current_state = get_relay_state()
    print(f"Aktueller Relaiszustand: {current_state}")

    if humidity > HUM_ON and current_state != "ON":
        print(f"Feuchte > {HUM_ON} → Relais AN")
        relay_on()
    elif humidity < HUM_OFF and current_state != "OFF":
        print(f"Feuchte < {HUM_OFF} → Relais AUS")
        relay_off()
    else:
        print("Keine Änderung erforderlich.")


if __name__ == "__main__":
    main()
