#!/usr/bin/env python3
"""
Standalone-Test fuer MLX90614 mit CloudWatcher-Tsky-Berechnung

- Keine Sonderzeichen (ASCII only)
- Kein askutils
- Kein config.py
- Kein Influx
- Ausgabe nur auf Konsole
"""

import time
import math
import argparse

try:
    import smbus
except ImportError:
    smbus = None


# -------------------------------------------------
# I2C-Konfiguration
# -------------------------------------------------
I2C_BUS  = 1
I2C_ADDR = 0x5A

# MLX90614 Register
REG_TA    = 0x06  # Ambient
REG_TOBJ1 = 0x07  # Object

# -------------------------------------------------
# CloudWatcher Default-Koeffizienten
# K1=100, K2..K7=0 -> Tsky = Ts - Ta
# alle K = 0       -> Tsky = Ts
# -------------------------------------------------
DEFAULT_K1 = 100.0
DEFAULT_K2 = 0.0
DEFAULT_K3 = 0.0
DEFAULT_K4 = 0.0
DEFAULT_K5 = 0.0
DEFAULT_K6 = 0.0
DEFAULT_K7 = 0.0

_bus = None


# -------------------------------------------------
# MLX90614 Low-Level
# -------------------------------------------------
def get_bus():
    global _bus
    if _bus is None:
        if smbus is None:
            raise RuntimeError("python3-smbus ist nicht installiert")
        _bus = smbus.SMBus(I2C_BUS)
    return _bus


def read_raw(reg: int) -> int:
    bus = get_bus()
    data = bus.read_i2c_block_data(I2C_ADDR, reg, 3)
    lsb, msb = data[0], data[1]
    return (msb << 8) | lsb


def raw_to_celsius(raw: int) -> float:
    return (raw * 0.02) - 273.15


def read_temp_celsius(reg: int) -> float:
    raw = read_raw(reg)
    t = raw_to_celsius(raw)

    if not (-70.0 <= t <= 380.0):
        swapped = ((raw & 0xFF) << 8) | (raw >> 8)
        t_swapped = raw_to_celsius(swapped)
        if -70.0 <= t_swapped <= 380.0:
            t = t_swapped

    return round(t, 2)


def sensor_connected() -> bool:
    try:
        t_amb = read_temp_celsius(REG_TA)
        return -40.0 <= t_amb <= 125.0
    except Exception:
        return False


def read_mlx90614_avg():
    amb1 = read_temp_celsius(REG_TA)
    obj1 = read_temp_celsius(REG_TOBJ1)

    time.sleep(0.05)

    amb2 = read_temp_celsius(REG_TA)
    obj2 = read_temp_celsius(REG_TOBJ1)

    ambient = round((amb1 + amb2) / 2.0, 2)
    object_ = round((obj1 + obj2) / 2.0, 2)
    return ambient, object_


# -------------------------------------------------
# CloudWatcher Modell
# -------------------------------------------------
def sgn(x: float) -> int:
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


def compute_tsky_cloudwatcher(
    Ts: float,
    Ta: float,
    K1: float = DEFAULT_K1,
    K2: float = DEFAULT_K2,
    K3: float = DEFAULT_K3,
    K4: float = DEFAULT_K4,
    K5: float = DEFAULT_K5,
    K6: float = DEFAULT_K6,
    K7: float = DEFAULT_K7,
) -> float:

    T0 = K2 / 10.0
    d = abs(T0 - Ta)

    if K6 == 0.0:
        T67 = 0.0
    else:
        if d < 1.0:
            T67 = sgn(K6) * sgn(Ta - T0) * d
        else:
            T67 = (K6 / 10.0) * sgn(Ta - T0) * (math.log(d) / math.log(10.0) + K7 / 100.0)

    term1 = (K1 / 100.0) * (Ta - T0)
    term2 = (K3 / 100.0) * (math.exp((K4 / 1000.0) * Ta) ** (K5 / 100.0))

    Td = term1 + term2 + T67
    Tsky = Ts - Td
    return float(Tsky)


def classify_cloudiness(Tsky: float) -> int:
    if Tsky <= -25.0:
        return 0
    elif Tsky <= -18.0:
        return 1
    elif Tsky <= -12.0:
        return 2
    else:
        return 3


# -------------------------------------------------
# CLI / Main
# -------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(description="MLX90614 CloudWatcher Test ASCII")
    p.add_argument("--bus", type=int, default=I2C_BUS)
    p.add_argument("--addr", type=lambda x: int(x, 0), default=I2C_ADDR)
    p.add_argument("--k1", type=float, default=DEFAULT_K1)
    p.add_argument("--k2", type=float, default=DEFAULT_K2)
    p.add_argument("--k3", type=float, default=DEFAULT_K3)
    p.add_argument("--k4", type=float, default=DEFAULT_K4)
    p.add_argument("--k5", type=float, default=DEFAULT_K5)
    p.add_argument("--k6", type=float, default=DEFAULT_K6)
    p.add_argument("--k7", type=float, default=DEFAULT_K7)
    return p.parse_args()


def main():
    global I2C_BUS, I2C_ADDR, _bus
    args = parse_args()

    I2C_BUS = args.bus
    I2C_ADDR = args.addr
    _bus = None

    print("")
    print("MLX90614 CloudWatcher Test (ASCII)")
    print("I2C Bus  :", I2C_BUS)
    print("I2C Addr :", hex(I2C_ADDR))
    print("")

    print("CloudWatcher Koeffizienten:")
    print("K1=", args.k1, "K2=", args.k2, "K3=", args.k3,
          "K4=", args.k4, "K5=", args.k5, "K6=", args.k6, "K7=", args.k7)
    print("")

    if not sensor_connected():
        print("Fehler: MLX90614 nicht erreichbar oder unplausible Werte")
        print("Hinweise:")
        print("- I2C aktivieren (raspi-config)")
        print("- Adresse pruefen: i2cdetect -y 1")
        print("- python3-smbus installieren")
        return

    Ta, Ts = read_mlx90614_avg()

    delta_simple = Ts - Ta
    Tsky = compute_tsky_cloudwatcher(
        Ts=Ts,
        Ta=Ta,
        K1=args.k1,
        K2=args.k2,
        K3=args.k3,
        K4=args.k4,
        K5=args.k5,
        K6=args.k6,
        K7=args.k7,
    )

    cloud_state = classify_cloudiness(Tsky)

    print("Messwerte:")
    print("Ambient Ta        :", Ta, "GradC")
    print("Object  Ts        :", Ts, "GradC")
    print("Delta Ts-Ta       :", round(delta_simple, 2), "GradC")
    print("Tsky korrigiert   :", round(Tsky, 2), "GradC")
    print("Bewoelkung (int)  :", cloud_state)
    print("")
    print("Bewoelkungsskala:")
    print("0 = klar")
    print("1 = leicht bewoelkt")
    print("2 = stark bewoelkt")
    print("3 = bedeckt")
    print("")


if __name__ == "__main__":
    main()
