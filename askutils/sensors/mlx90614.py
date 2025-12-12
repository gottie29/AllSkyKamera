import time
import smbus
from askutils import config

# Erwartete Config-Felder (mit Defaults, falls nicht vorhanden)
I2C_ADDR = getattr(config, "MLX90614_I2C_ADDRESS", 0x5A)
I2C_BUS  = 1

# MLX90614 Register
REG_TA    = 0x06  # Ambient
REG_TOBJ1 = 0x07  # Object 1

_bus = None

def _get_bus():
    global _bus
    if _bus is None:
        _bus = smbus.SMBus(I2C_BUS)
    return _bus

def _read_raw(reg: int) -> int:
    """
    Liest 3 Bytes (LSB, MSB, PEC) und kombiniert LSB/MSB zum 16-bit Wert.
    Wir ignorieren hier bewusst den PEC. Bei Bedarf koennte man ihn pruefen.
    """
    bus = _get_bus()
    data = bus.read_i2c_block_data(I2C_ADDR, reg, 3)  # [lsb, msb, pec]
    lsb, msb = data[0], data[1]
    return (msb << 8) | lsb

def _raw_to_celsius(raw: int) -> float:
    # Formel laut Datenblatt: Grad_C = raw * 0.02 - 273.15
    return (raw * 0.02) - 273.15

def _read_temp_celsius(reg: int) -> float:
    raw = _read_raw(reg)
    t = _raw_to_celsius(raw)

    # Plausibilitaetscheck; bei Byte-Order-Issue einmal tauschen
    if not (-70.0 <= t <= 380.0):
        swapped = ((raw & 0xFF) << 8) | (raw >> 8)
        t_swapped = _raw_to_celsius(swapped)
        if -70.0 <= t_swapped <= 380.0:
            t = t_swapped
    return round(t, 2)

def is_connected() -> bool:
    """
    Schneller Check: einmal Ambient lesen und auf plausiblen Bereich pruefen.
    """
    try:
        t_amb = _read_temp_celsius(REG_TA)
        return -70.0 <= t_amb <= 125.0
    except Exception:
        return False

def read_mlx90614() -> dict:
    """
    Liefert ein Dict mit 'ambient' und 'object' in Grad_C.
    """
    amb = _read_temp_celsius(REG_TA)
    obj = _read_temp_celsius(REG_TOBJ1)

    # Minimale Entprellung / Stabilisierung (optional)
    # kurz warten und zweiten Messwert mitteln, um Ausreisser zu daempfen
    time.sleep(0.05)
    amb2 = _read_temp_celsius(REG_TA)
    obj2 = _read_temp_celsius(REG_TOBJ1)

    ambient = round((amb + amb2) / 2.0, 2)
    object_ = round((obj + obj2) / 2.0, 2)

    return {
        "ambient": ambient,
        "object": object_,
    }
