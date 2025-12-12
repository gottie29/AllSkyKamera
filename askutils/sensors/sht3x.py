# askutils/sensors/sht3x.py

import time
import math
import smbus2
from .. import config

I2C_BUS = 1
I2C_ADDR = config.SHT3X_I2C_ADDRESS

# Single shot command (high repeatability, no clock stretching)
CMD_SINGLE_SHOT = (0x24, 0x00)

# Offsets from config.py
TEMP_OFFSET = getattr(config, "SHT3X_TEMP_OFFSET", 0.0)
HUM_OFFSET  = getattr(config, "SHT3X_HUM_OFFSET", 0.0)


class SHT3x:
    """SHT3x (SHT30 / SHT31 / SHT35) sensor readout class"""

    def __init__(self):
        try:
            self.bus = smbus2.SMBus(I2C_BUS)
        except Exception as e:
            raise RuntimeError(f"Could not open I2C bus: {e}")

    def _read_raw(self):
        """
        Perform a single-shot measurement and return raw temperature
        and humidity values (without CRC check).
        """
        # Send single shot command
        try:
            self.bus.write_i2c_block_data(
                I2C_ADDR,
                CMD_SINGLE_SHOT[0],
                [CMD_SINGLE_SHOT[1]],
            )
        except Exception as e:
            raise RuntimeError(f"I2C error while sending SHT3x command: {e}")

        # Typical conversion time is < 15 ms, we wait a bit more
        time.sleep(0.020)

        # Read 6 bytes: T_MSB, T_LSB, T_CRC, H_MSB, H_LSB, H_CRC
        try:
            data = self.bus.read_i2c_block_data(I2C_ADDR, 0x00, 6)
        except Exception as e:
            raise RuntimeError(f"I2C error while reading SHT3x data: {e}")

        if len(data) != 6:
            raise RuntimeError(
                f"Unexpected SHT3x data length: {len(data)}, expected 6"
            )

        raw_t = (data[0] << 8) | data[1]
        raw_h = (data[3] << 8) | data[4]

        return raw_t, raw_h

    def read_temperature(self):
        raw_t, _ = self._read_raw()
        # Datasheet formula
        temp_c = -45.0 + (175.0 * (raw_t / 65535.0))
        return round(temp_c + TEMP_OFFSET, 2)

    def read_humidity(self):
        _, raw_h = self._read_raw()
        # Datasheet formula
        hum = 100.0 * (raw_h / 65535.0)
        hum = max(0.0, min(100.0, hum))
        return round(hum + HUM_OFFSET, 2)

    def read(self):
        t = self.read_temperature()
        # very short pause between reads to be nice to the sensor
        time.sleep(0.01)
        h = self.read_humidity()
        return t, h


def calculate_dew_point(temp_c, hum):
    """Magnus formula for dew point in degree C."""
    if hum <= 0.0:
        return float("nan")

    a = 17.62
    b = 243.12
    alpha = ((a * temp_c) / (b + temp_c)) + math.log(hum / 100.0)
    return round((b * alpha) / (a - alpha), 2)
