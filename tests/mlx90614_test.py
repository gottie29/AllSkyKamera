#!/usr/bin/python
import smbus
import time
import datetime

# === Grundeinstellungen ===
DEVICE = 0x5A  # Standard-I2C-Adresse des MLX90614
bus = smbus.SMBus(1)

# === Register ===
MLX90614_TA = 0x06    # Ambient Temperature
MLX90614_TOBJ1 = 0x07 # Object Temperature 1
MLX90614_TOBJ2 = 0x08 # Object Temperature 2 (optional)

def read_word(addr, reg):
    """Liest ein 16-Bit-Wort aus dem angegebenen Register."""
    data = bus.read_word_data(addr, reg)
    # Die Bytes sind vertauscht -> korrigieren
    return ((data & 0xFF) << 8) | (data >> 8)

def read_temperature(addr, reg):
    """Liest Temperatur in °C aus."""
    raw = read_word(addr, reg)
    temp = (raw * 0.02) - 273.15  # Umrechnung laut Datenblatt
    return round(temp, 2)

def main():
    print("=== MLX90614 Temperatursensor Test ===")
    try:
        while True:
            ta = read_temperature(DEVICE, MLX90614_TA)
            tobj1 = read_temperature(DEVICE, MLX90614_TOBJ1)

            zeit = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{zeit}] Umgebung: {ta:.2f} °C | Objekt: {tobj1:.2f} °C")

            time.sleep(2)

    except KeyboardInterrupt:
        print("\nBeendet durch Benutzer.")
    except OSError as e:
        print(f"I2C-Fehler: {e}")

if __name__ == "__main__":
    main()

