# askutils/sensors/htu21.py

import time
import smbus2
import math
from .. import config

I2C_BUS = 1
I2C_ADDR = config.HTU21_I2C_ADDRESS

# Commands (Hold Master Mode)
CMD_TEMP_HOLD = 0xE3
CMD_HUM_HOLD  = 0xE5
CMD_RESET     = 0xFE

# Offsets aus config.py
TEMP_OFFSET = getattr(config, "HTU21_TEMP_OFFSET", 0.0)
HUM_OFFSET  = getattr(config, "HTU21_HUM_OFFSET", 0.0)

class HTU21:
    """HTU21 / Si7021 Sensor-Leseklasse"""

    def __init__(self):
        try:
            self.bus = smbus2.SMBus(I2C_BUS)
        except Exception as e:
            raise RuntimeError(f"I2C-Bus konnte nicht geoeffnet werden: {e}")

        # Soft Reset (optional)
        try:
            self.bus.write_byte(I2C_ADDR, CMD_RESET)
            time.sleep(0.05)
        except Exception:
            pass

    def _read_raw(self, command):
        """Liest Rohdaten (Hold Master Mode)"""
        try:
            data = self.bus.read_i2c_block_data(I2C_ADDR, command, 2)
        except Exception as e:
            raise RuntimeError(f"I2C-Fehler beim Lesen von Kommando 0x{command:02X}: {e}")

        raw = (data[0] << 8) | data[1]
        raw &= 0xFFFC
        return raw

    def read_temperature(self):
        raw = self._read_raw(CMD_TEMP_HOLD)
        temp = -46.85 + (175.72 * raw / 65536.0)
        return round(temp + TEMP_OFFSET, 2)

    def read_humidity(self):
        raw = self._read_raw(CMD_HUM_HOLD)
        hum = -6.0 + (125.0 * raw / 65536.0)
        hum = max(0.0, min(100.0, hum))  # clamp
        return round(hum + HUM_OFFSET, 2)

    def read(self):
        t = self.read_temperature()
        time.sleep(0.02)
        h = self.read_humidity()
        return t, h


def calculate_dew_point(temp_c, hum):
    """Magnus-Formel"""
    a = 17.62
    b = 243.12
    alpha = ((a * temp_c) / (b + temp_c)) + math.log(hum / 100.0)
    return round((b * alpha) / (a - alpha), 2)
