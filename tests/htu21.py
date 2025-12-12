#!/usr/bin/env python3
"""
HTU21 / GY-21 (Si7021 / HTU21D) – einfacher Test fuer Raspberry Pi

- Liest einmal Temperatur (Grad_C) und relative Luftfeuchtigkeit (% rF)
- Verwendet I²C-Bus 1 und Adresse 0x40 (Standard fuer GY-21 / HTU21D)
- Nutzt den Hold-Master-Modus (0xE3 / 0xE5) wie im funktionierenden GY-21-Skript
- Berechnet zusaetzlich den Taupunkt und beendet sich danach.
"""

import sys
import time
import math
import datetime

# ---------------------------------------------------------
# Abhaengigkeiten
# ---------------------------------------------------------
try:
    import smbus2
except ImportError:
    print("Fehler: smbus2 ist nicht installiert.")
    print("Installiere es z.B. mit:")
    print("  sudo apt install python3-smbus")
    print("oder:")
    print("  pip3 install smbus2")
    sys.exit(1)

# ---------------------------------------------------------
# Konfiguration Sensor
# ---------------------------------------------------------
I2C_BUS = 1        # I²C-Bus beim Raspberry Pi (meistens 1)
I2C_ADDR = 0x40    # Standardadresse des GY-21 (Si7021/HTU21D)

# Hold-Master-Kommandos (wie in deinem funktionierenden Script)
CMD_TEMP_HOLD = 0xE3  # Temperatur messen (Hold Master)
CMD_HUM_HOLD  = 0xE5  # Luftfeuchte messen (Hold Master)
CMD_RESET     = 0xFE  # Soft-Reset


class Htu21Sensor:
    """Klasse zum Auslesen des HTU21 / GY-21 (Si7021 / HTU21D) Sensors."""

    def __init__(self, bus: int = I2C_BUS, address: int = I2C_ADDR):
        self.address = address
        self.bus_num = bus

        try:
            self.bus = smbus2.SMBus(bus)
        except FileNotFoundError:
            raise RuntimeError(
                f"I²C-Bus {bus} wurde nicht gefunden.\n"
                "Ist I²C auf dem Raspberry Pi aktiviert?\n"
                "-> sudo raspi-config (Schnittstellen / I2C aktivieren)"
            )
        except Exception as e:
            raise RuntimeError(f"Fehler beim oeffnen des I²C-Bus {bus}: {e}")

        # Soft-Reset versuchen – viele GY-21-Boards moegen das
        try:
            self.bus.write_byte(self.address, CMD_RESET)
            time.sleep(0.05)  # kurze Pause nach Reset
        except OSError as e:
            # Kein harter Abbruch – nur Hinweis
            print(f"[Warnung] Soft-Reset des HTU21/GY-21 fehlgeschlagen: {e}")

    def _read_raw_hold(self, command: int) -> int:
        """
        Messung im Hold-Master-Modus:
        - read_i2c_block_data(addr, command, 2)
        - Der SMBus-Treiber sendet das Kommando und wartet auf die Antwort.

        Gibt den rohen Messwert (ohne Statusbits) zurueck
        oder wirft RuntimeError bei Problemen.
        """
        try:
            data = self.bus.read_i2c_block_data(self.address, command, 2)
        except OSError as e:
            raise RuntimeError(
                f"Konnte Messdaten nicht lesen (Hold-Mode, cmd=0x{command:02X}) "
                f"vom Sensor an Adresse 0x{self.address:02X} auf Bus {self.bus_num}: {e}"
            ) from e

        if len(data) != 2:
            raise RuntimeError(
                f"Unerwartete Anzahl Bytes vom Sensor (erwartet 2, bekommen {len(data)})."
            )

        raw = (data[0] << 8) | data[1]
        raw &= 0xFFFC  # Statusbits auf 0 setzen
        return raw

    def read_temperature(self) -> float:
        """Temperatur in Grad_C auslesen (wirft RuntimeError bei Fehler)."""
        raw = self._read_raw_hold(CMD_TEMP_HOLD)

        # Formel laut Datenblatt:
        # T = -46.85 + 175.72 * (raw / 2^16)
        temp_c = -46.85 + (175.72 * raw / 65536.0)
        return temp_c

    def read_humidity(self) -> float:
        """Relative Luftfeuchtigkeit in % auslesen (wirft RuntimeError bei Fehler)."""
        raw = self._read_raw_hold(CMD_HUM_HOLD)

        # Formel laut Datenblatt:
        # RH = -6 + 125 * (raw / 2^16)
        rh = -6.0 + (125.0 * raw / 65536.0)
        # Begrenzen auf physikalisch sinnvollen Bereich
        rh = max(0.0, min(100.0, rh))
        return rh

    def read(self):
        """Temperatur und Feuchte zusammen auslesen (wirft RuntimeError bei Fehler)."""
        t = self.read_temperature()
        time.sleep(0.02)  # kleine Pause zwischen den Messungen
        h = self.read_humidity()
        return t, h


def calculate_dew_point(temp_c: float, humidity_percent: float) -> float:
    """Taupunkt (Grad_C) aus Temperatur und relativer Luftfeuchte (Magnus-Formel)."""
    if humidity_percent <= 0:
        return float("nan")

    a = 17.62
    b = 243.12
    alpha = ((a * temp_c) / (b + temp_c)) + math.log(humidity_percent / 100.0)
    dew_point = (b * alpha) / (a - alpha)
    return round(dew_point, 2)


def main():
    print("=== HTU21 / GY-21 (Si7021 / HTU21D) Test ===")
    print(f"Verwende I²C-Bus {I2C_BUS} und Adresse 0x{I2C_ADDR:02X}")
    print("Stelle sicher, dass der Sensor angeschlossen ist und I²C aktiviert ist (raspi-config).")
    print()

    try:
        sensor = Htu21Sensor()
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        print("Tipp: Mit 'sudo i2cdetect -y 1' nach I²C-Geraeten suchen.")
        sys.exit(1)

    try:
        temp_c, rh = sensor.read()
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    now = datetime.datetime.now().isoformat(timespec="seconds")
    dew_point = calculate_dew_point(temp_c, rh)

    print(f"Timestamp   : {now}")
    print(f"Temperature : {temp_c:6.2f} Grad_C")
    print(f"Humidity    : {rh:6.2f} % rF")
    print(f"Dew point   : {dew_point:6.2f} Grad_C")
    print()
    print("Test finished. Exiting.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDurch Benutzer abgebrochen.")
        sys.exit(0)
    except Exception as exc:
        print(f"[UNEXPECTED ERROR] {exc}")
        sys.exit(1)
