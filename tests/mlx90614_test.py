#!/usr/bin/python
import smbus
import time
import datetime

# === Einstellungen ===
DEVICE = 0x5A          # Standardadresse des MLX90614
BUSNUM = 1             # I2C-Bus (Raspberry Pi: 1)
bus = smbus.SMBus(BUSNUM)

# === Register-Adressen ===
REG_TA    = 0x06       # Ambient (Umgebung)
REG_TOBJ1 = 0x07       # Objekt 1
REG_TOBJ2 = 0x08       # Objekt 2 (falls vorhanden)

# --- (optional) PEC-Berechnung, falls du Daten absichern willst ---
def crc8(data):
    """ SMBus PEC (CRC-8) mit Polynom 0x07. """
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
    """
    Liest 3 Bytes: LSB, MSB, PEC. Kombiniert zu 16-bit Rohwert (LSB + MSB<<8).
    Wenn check_pec=True, wird der PEC geprüft (wirft bei Fehler ValueError).
    """
    # Für PEC-Berechnung braucht man die komplette SMBus-Transaktion:
    # [SlaveAddr(W), Command, SlaveAddr(R), LSB, MSB, PEC]
    data = bus.read_i2c_block_data(addr, reg, 3)  # [lsb, msb, pec]
    lsb, msb, pec_rx = data[0], data[1], data[2]
    raw = (msb << 8) | lsb  # korrekt für MLX90614

    if check_pec:
        # Paket für PEC: [addr<<1 | 0 (W), reg, addr<<1 | 1 (R), lsb, msb]
        pkt = [(addr << 1) | 0, reg, (addr << 1) | 1, lsb, msb]
        pec_calc = crc8(pkt)
        if pec_calc != pec_rx:
            raise ValueError(f"PEC mismatch (got {pec_rx:#04x}, expected {pec_calc:#04x})")

    return raw

def raw_to_celsius(raw):
    """ Umrechnung gemäß Datenblatt: °C = raw * 0.02 - 273.15 """
    return (raw * 0.02) - 273.15

def read_temperature(addr, reg, check_pec=False):
    """
    Liest Temperatur in °C. Versucht bei unplausiblen Werten Byte-Swap-Fallback.
    """
    raw = read_raw_pec(addr, reg, check_pec=check_pec)
    t = raw_to_celsius(raw)

    # Plausibilitätscheck: Ambient meist -40..125°C, Objekt sinnvoll -70..380°C
    if not (-70.0 <= t <= 380.0):
        # Fallback: Byte-Order tauschen (falls Treiber die Bytes schon gedreht hat)
        swapped = ((raw & 0xFF) << 8) | (raw >> 8)
        t_swapped = raw_to_celsius(swapped)
        # Nur übernehmen, wenn plausibel
        if -70.0 <= t_swapped <= 380.0:
            t = t_swapped
    return round(t, 2)

def main():
    print("=== MLX90614 Temperatursensor Test ===")
    try:
        while True:
            ta    = read_temperature(DEVICE, REG_TA,    check_pec=False)
            tobj1 = read_temperature(DEVICE, REG_TOBJ1, check_pec=False)
            zeit  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{zeit}] Umgebung: {ta:.2f} °C | Objekt: {tobj1:.2f} °C")
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nBeendet.")
    except OSError as e:
        print(f"I2C-Fehler: {e}")
    except ValueError as e:
        print(f"Datenfehler: {e}")

if __name__ == "__main__":
    main()

