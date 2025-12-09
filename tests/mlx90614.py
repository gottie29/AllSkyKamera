#!/usr/bin/env python3
"""
MLX90614 temperature sensor test script

- Interface: I2C bus 1 (smbus)
- Reads ambient and object temperature a few times and exits
- ASCII-only, English messages
"""

import time
import datetime
import sys

# Try to import smbus (I2C library)
try:
    import smbus
except ImportError:
    print("ERROR: Python smbus library is not installed.")
    print("Install on Raspberry Pi with:")
    print("  sudo apt-get update")
    print("  sudo apt-get install python3-smbus i2c-tools")
    sys.exit(1)

# Settings
DEVICE_ADDRESS = 0x5A   # Default I2C address of MLX90614
BUS_NUMBER     = 1      # I2C bus 1 on Raspberry Pi

try:
    bus = smbus.SMBus(BUS_NUMBER)
except Exception as e:
    print("ERROR: Could not open I2C bus", BUS_NUMBER)
    print("Hint: enable I2C via 'sudo raspi-config' and check wiring.")
    print("Exception:", e)
    sys.exit(1)

# Register addresses
REG_TA    = 0x06  # Ambient temperature
REG_TOBJ1 = 0x07  # Object 1 temperature
REG_TOBJ2 = 0x08  # Object 2 (if available)


def crc8(data):
    """
    SMBus PEC (CRC-8) with polynomial 0x07.
    Used for optional data integrity check.
    """
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
    Read 3 bytes: LSB, MSB, PEC.
    Combine to 16-bit raw value (LSB + MSB << 8).
    If check_pec=True, validate PEC and raise ValueError on mismatch.
    """
    data = bus.read_i2c_block_data(addr, reg, 3)  # [lsb, msb, pec]
    lsb, msb, pec_rx = data[0], data[1], data[2]
    raw = (msb << 8) | lsb

    if check_pec:
        # Packet for PEC: [addr<<1 | 0 (W), reg, addr<<1 | 1 (R), lsb, msb]
        pkt = [(addr << 1) | 0, reg, (addr << 1) | 1, lsb, msb]
        pec_calc = crc8(pkt)
        if pec_calc != pec_rx:
            raise ValueError(
                "PEC mismatch (got 0x%02X, expected 0x%02X)" % (pec_rx, pec_calc)
            )

    return raw


def raw_to_celsius(raw):
    """Convert raw value to degrees Celsius according to datasheet."""
    return (raw * 0.02) - 273.15


def read_temperature(addr, reg, check_pec=False):
    """
    Read temperature in degC.
    If value is not plausible, try byte-swap as fallback.
    """
    raw = read_raw_pec(addr, reg, check_pec=check_pec)
    t = raw_to_celsius(raw)

    # Plausibility check: MLX90614 valid approx. range -70..380 degC
    if not (-70.0 <= t <= 380.0):
        swapped = ((raw & 0xFF) << 8) | (raw >> 8)
        t_swapped = raw_to_celsius(swapped)
        if -70.0 <= t_swapped <= 380.0:
            t = t_swapped

    return round(t, 2)


def main():
    print("MLX90614 temperature sensor test")
    print("Interface: I2C bus %d, address 0x%02X" % (BUS_NUMBER, DEVICE_ADDRESS))
    print("This test will read a few values and then exit.\n")

    samples = 5

    try:
        for i in range(samples):
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            try:
                ta = read_temperature(DEVICE_ADDRESS, REG_TA, check_pec=False)
                tobj1 = read_temperature(DEVICE_ADDRESS, REG_TOBJ1, check_pec=False)
            except OSError as e:
                print("[%s] I2C error while reading sensor: %s" % (timestamp, e))
                print("Hint: check I2C wiring, bus number and device address.")
                break
            except ValueError as e:
                print("[%s] Data error: %s" % (timestamp, e))
                break

            print(
                "[%s] Ambient: %.2f C | Object: %.2f C"
                % (timestamp, ta, tobj1)
            )
            time.sleep(2.0)

        print("\nTest finished. Exiting.")

    except KeyboardInterrupt:
        print("\nAborted by user.")


if __name__ == "__main__":
    main()
