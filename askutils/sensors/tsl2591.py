import board
import busio
import math
import adafruit_tsl2591
from askutils import config

def is_connected():
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        sensor = adafruit_tsl2591.TSL2591(i2c)
        return sensor.lux is not None
    except Exception:
        return False

def read_tsl2591():
    i2c = busio.I2C(board.SCL, board.SDA)
    sensor = adafruit_tsl2591.TSL2591(i2c)

    lux = sensor.lux or 0.0001
    visible = sensor.visible or 0.0001
    infrared = sensor.infrared or 0.0001
    full = sensor.full_spectrum or 0.0001

    skybright = 22.0 - 2.5 * math.log10(lux) + config.TSL2591_SQM_CORRECTION
    skybright2 = 22.0 - 2.5 * math.log10(visible) + config.TSL2591_SQM_CORRECTION

    if skybright2 < config.TSL2591_SQM2_LIMIT:
        skybright2 = 0.0001

    return {
        "lux": round(lux, 2),
        "visible": int(visible),
        "infrared": int(infrared),
        "full": int(full),
        "sqm": round(skybright, 2),
        "sqm2": round(skybright2, 2)
    }
