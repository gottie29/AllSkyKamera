# askutils/sensors/bme280.py

import smbus
import time
import math
from ctypes import c_short, c_byte, c_ubyte
from .. import config


bus = smbus.SMBus(1)
DEVICE = config.BME280_I2C_ADDRESS

def get_chip_id(addr=DEVICE):
    REG_ID = 0xD0
    return bus.read_i2c_block_data(addr, REG_ID, 2)

def read_bme280(addr=DEVICE):
    if not config.BME280_ENABLED:
        raise RuntimeError("BME280 ist in config.py deaktiviert!")

def getShort(data, index):
    return c_short((data[index+1] << 8) + data[index]).value

def getUShort(data, index):
    return (data[index+1] << 8) + data[index]

def getChar(data, index):
    result = data[index]
    if result > 127:
        result -= 256
    return result

def getUChar(data, index):
    return data[index] & 0xFF

def get_chip_id(addr=DEVICE):
    REG_ID = 0xD0
    return bus.read_i2c_block_data(addr, REG_ID, 2)

def read_bme280(addr=DEVICE):
    REG_DATA = 0xF7
    REG_CONTROL = 0xF4
    REG_CONFIG  = 0xF5
    REG_CONTROL_HUM = 0xF2
    OVERSAMPLE_TEMP = 2
    OVERSAMPLE_PRES = 2
    OVERSAMPLE_HUM = 2
    MODE = 1

    bus.write_byte_data(addr, REG_CONTROL_HUM, OVERSAMPLE_HUM)
    control = OVERSAMPLE_TEMP<<5 | OVERSAMPLE_PRES<<2 | MODE
    bus.write_byte_data(addr, REG_CONTROL, control)

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

    wait_time = 1.25 + (2.3 * OVERSAMPLE_TEMP) + ((2.3 * OVERSAMPLE_PRES) + 0.575) + ((2.3 * OVERSAMPLE_HUM)+0.575)
    time.sleep(wait_time / 1000)

    data = bus.read_i2c_block_data(addr, REG_DATA, 8)
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
    pressure = 0 if var1 == 0 else ((1048576.0 - pres_raw - var2 / 4096.0) * 6250.0 / var1)
    var1 = dig_P9 * pressure * pressure / 2147483648.0
    var2 = pressure * dig_P8 / 32768.0
    pressure = (pressure + (var1 + var2 + dig_P7) / 16.0) / 100.0

    humidity = t_fine - 76800.0
    humidity = (hum_raw - (dig_H4 * 64.0 + dig_H5 / 16384.0 * humidity)) * (
        dig_H2 / 65536.0 * (1.0 + dig_H6 / 67108864.0 * humidity * (1.0 + dig_H3 / 67108864.0 * humidity))
    )
    humidity = humidity * (1.0 - dig_H1 * humidity / 524288.0)
    humidity = max(0, min(humidity, 100))

    return round(temperature, 2), round(pressure, 2), round(humidity, 2)

def calculate_dew_point(temp, hum):
    a = 17.62
    b = 243.12
    alpha = ((a * temp) / (b + temp)) + math.log(hum / 100.0)
    return round((b * alpha) / (a - alpha), 2)
