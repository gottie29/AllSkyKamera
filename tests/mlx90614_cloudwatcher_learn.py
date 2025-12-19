#!/usr/bin/env python3
"""
MLX90614 CloudWatcher Standalone mit Online-Learning (ASCII only)

Phase 1:
- Schwellenwerte thr_clear/thr_light/thr_heavy werden nach jedem Lauf leicht angepasst

Phase 2:
- Wenn genug Samples vorhanden sind, werden K1 und K2 minimal angepasst
- K3..K7 bleiben unveraendert
- Grenzen und kleine Lernrate fuer Stabilitaet
"""

import time
import math
import json
import csv
import os
from datetime import datetime

try:
    import smbus
except ImportError:
    smbus = None

COEFFS_FILE = "coeffs.json"
SAMPLES_FILE = "mlx90614_samples.csv"

I2C_BUS = 1
I2C_ADDR = 0x5A

REG_TA = 0x06
REG_TOBJ1 = 0x07

_bus = None


# -----------------------------
# MLX90614 functions
# -----------------------------
def get_bus():
    global _bus
    if _bus is None:
        if smbus is None:
            raise RuntimeError("python3-smbus fehlt. Install: sudo apt install python3-smbus i2c-tools")
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

    Ta = round((amb1 + amb2) / 2.0, 2)
    Ts = round((obj1 + obj2) / 2.0, 2)
    return Ta, Ts


# -----------------------------
# CloudWatcher model
# -----------------------------
def sgn(x: float) -> int:
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


def compute_tsky_cloudwatcher(Ts, Ta, K1, K2, K3, K4, K5, K6, K7) -> float:
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
    return float(Ts - Td)


def classify_by_thresholds(Tsky, thr_clear, thr_light, thr_heavy) -> int:
    if Tsky <= thr_clear:
        return 0
    if Tsky <= thr_light:
        return 1
    if Tsky <= thr_heavy:
        return 2
    return 3


# -----------------------------
# coeffs load/save
# -----------------------------
def clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def enforce_threshold_order(c):
    a = float(c.get("thr_clear", -25.0))
    b = float(c.get("thr_light", -18.0))
    d = float(c.get("thr_heavy", -12.0))
    arr = sorted([a, b, d])
    c["thr_clear"], c["thr_light"], c["thr_heavy"] = arr[0], arr[1], arr[2]
    return c


def load_coeffs():
    if not os.path.exists(COEFFS_FILE):
        raise RuntimeError("coeffs.json fehlt: " + COEFFS_FILE)

    with open(COEFFS_FILE, "r", encoding="utf-8") as f:
        c = json.load(f)

    # K defaults
    c.setdefault("K1", 100.0); c.setdefault("K2", 0.0); c.setdefault("K3", 0.0)
    c.setdefault("K4", 0.0); c.setdefault("K5", 0.0); c.setdefault("K6", 0.0); c.setdefault("K7", 0.0)

    # thresholds defaults
    c.setdefault("thr_clear", -25.0); c.setdefault("thr_light", -18.0); c.setdefault("thr_heavy", -12.0)
    c.setdefault("learn_rate_thr", 0.15)

    # phase2 defaults
    c.setdefault("phase2_enabled", True)
    c.setdefault("min_samples_k", 80)
    c.setdefault("learn_rate_k", 0.02)
    c.setdefault("k1_min", 50.0); c.setdefault("k1_max", 150.0)
    c.setdefault("k2_min", -400.0); c.setdefault("k2_max", 400.0)

    # targets for labels
    c.setdefault("target_tsky_clear", -30.0)
    c.setdefault("target_tsky_light", -21.0)
    c.setdefault("target_tsky_heavy", -15.0)
    c.setdefault("target_tsky_overcast", -6.0)

    c = enforce_threshold_order(c)
    return c


def save_coeffs(c):
    c = enforce_threshold_order(c)
    # clamp K1/K2 to bounds
    c["K1"] = clamp(float(c["K1"]), float(c["k1_min"]), float(c["k1_max"]))
    c["K2"] = clamp(float(c["K2"]), float(c["k2_min"]), float(c["k2_max"]))

    with open(COEFFS_FILE, "w", encoding="utf-8") as f:
        json.dump(c, f, indent=2, sort_keys=True)


# -----------------------------
# logging
# -----------------------------
def append_sample(ts_iso, Ta, Ts, delta, Tsky, pred, label, coeffs):
    file_exists = os.path.exists(SAMPLES_FILE)
    with open(SAMPLES_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not file_exists:
            w.writerow([
                "timestamp_iso", "Ta_GradC", "Ts_GradC", "Delta_GradC", "Tsky_GradC",
                "pred", "label",
                "K1","K2","K3","K4","K5","K6","K7",
                "thr_clear","thr_light","thr_heavy"
            ])
        w.writerow([
            ts_iso, Ta, Ts, delta, round(Tsky, 4),
            pred, label,
            coeffs["K1"], coeffs["K2"], coeffs["K3"], coeffs["K4"], coeffs["K5"], coeffs["K6"], coeffs["K7"],
            coeffs["thr_clear"], coeffs["thr_light"], coeffs["thr_heavy"]
        ])


def read_samples_for_phase2(max_rows=4000):
    if not os.path.exists(SAMPLES_FILE):
        return []

    rows = []
    with open(SAMPLES_FILE, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            # keep minimal fields
            try:
                Ta = float(row["Ta_GradC"])
                Ts = float(row["Ts_GradC"])
                label = int(row["label"])
                rows.append((Ta, Ts, label))
            except Exception:
                pass

    # use recent rows (stability)
    if len(rows) > max_rows:
        rows = rows[-max_rows:]
    return rows


# -----------------------------
# Phase 1: thresholds update
# -----------------------------
def update_thresholds(coeffs, pred, label):
    lr = float(coeffs.get("learn_rate_thr", 0.15))

    thr_clear = float(coeffs["thr_clear"])
    thr_light = float(coeffs["thr_light"])
    thr_heavy = float(coeffs["thr_heavy"])

    if pred == label:
        return coeffs

    direction = 1.0 if pred < label else -1.0
    step = lr * max(0.2, min(2.0, abs(label - pred)))

    if pred == 0 or label == 0:
        thr_clear += direction * step
    elif pred == 1 or label == 1:
        thr_light += direction * step
    elif pred == 2 or label == 2:
        thr_heavy += direction * step
    else:
        thr_heavy += direction * step

    coeffs["thr_clear"] = thr_clear
    coeffs["thr_light"] = thr_light
    coeffs["thr_heavy"] = thr_heavy
    coeffs = enforce_threshold_order(coeffs)
    return coeffs


# -----------------------------
# Phase 2: learn K1/K2
# -----------------------------
def label_to_target(coeffs, label):
    if label == 0:
        return float(coeffs["target_tsky_clear"])
    if label == 1:
        return float(coeffs["target_tsky_light"])
    if label == 2:
        return float(coeffs["target_tsky_heavy"])
    return float(coeffs["target_tsky_overcast"])


def loss_mse(coeffs, samples, K1, K2):
    # MSE between computed Tsky and target per label
    K3 = float(coeffs["K3"]); K4 = float(coeffs["K4"]); K5 = float(coeffs["K5"])
    K6 = float(coeffs["K6"]); K7 = float(coeffs["K7"])

    if not samples:
        return 0.0

    s = 0.0
    n = 0
    for (Ta, Ts, label) in samples:
        tsky = compute_tsky_cloudwatcher(Ts, Ta, K1, K2, K3, K4, K5, K6, K7)
        target = label_to_target(coeffs, label)
        e = (tsky - target)
        s += e * e
        n += 1
    return s / float(n)


def phase2_update_k1k2(coeffs, samples):
    """
    One safe gradient step on K1/K2 using finite differences.
    """
    if not coeffs.get("phase2_enabled", True):
        return coeffs, False, "Phase2 disabled"

    min_samples = int(coeffs.get("min_samples_k", 80))
    if len(samples) < min_samples:
        return coeffs, False, "Not enough samples for Phase2"

    lr = float(coeffs.get("learn_rate_k", 0.02))

    k1 = float(coeffs["K1"])
    k2 = float(coeffs["K2"])

    # bounds
    k1_min = float(coeffs["k1_min"]); k1_max = float(coeffs["k1_max"])
    k2_min = float(coeffs["k2_min"]); k2_max = float(coeffs["k2_max"])

    # finite diff eps
    eps_k1 = 0.25
    eps_k2 = 1.0

    base = loss_mse(coeffs, samples, k1, k2)

    # gradient approx
    l1p = loss_mse(coeffs, samples, clamp(k1 + eps_k1, k1_min, k1_max), k2)
    l1m = loss_mse(coeffs, samples, clamp(k1 - eps_k1, k1_min, k1_max), k2)
    g1 = (l1p - l1m) / (2.0 * eps_k1)

    l2p = loss_mse(coeffs, samples, k1, clamp(k2 + eps_k2, k2_min, k2_max))
    l2m = loss_mse(coeffs, samples, k1, clamp(k2 - eps_k2, k2_min, k2_max))
    g2 = (l2p - l2m) / (2.0 * eps_k2)

    # step (clipped)
    new_k1 = clamp(k1 - lr * g1, k1_min, k1_max)
    new_k2 = clamp(k2 - lr * g2, k2_min, k2_max)

    new_loss = loss_mse(coeffs, samples, new_k1, new_k2)

    # accept only if improves (or very small change)
    if new_loss <= base:
        coeffs["K1"] = float(new_k1)
        coeffs["K2"] = float(new_k2)
        return coeffs, True, "Phase2 updated (loss improved)"
    else:
        # if it got worse, do nothing
        return coeffs, False, "Phase2 skipped (no improvement)"


# -----------------------------
# User prompt
# -----------------------------
def prompt_label():
    print("")
    print("Bitte gib den echten Wolkenstatus ein:")
    print("0 = klar")
    print("1 = leicht bewoelkt")
    print("2 = stark bewoelkt")
    print("3 = bedeckt")
    while True:
        s = input("Dein Label (0-3, oder Enter zum Abbrechen): ").strip()
        if s == "":
            return None
        if s in ("0", "1", "2", "3"):
            return int(s)
        print("Ungueltig. Bitte 0-3 eingeben oder Enter.")


def main():
    coeffs = load_coeffs()

    print("")
    print("MLX90614 CloudWatcher Online-Learning (ASCII)")
    print("I2C Bus  :", I2C_BUS)
    print("I2C Addr :", hex(I2C_ADDR))
    print("")
    print("Aktuelle Koeffizienten:")
    print("K1=", coeffs["K1"], "K2=", coeffs["K2"], "K3=", coeffs["K3"],
          "K4=", coeffs["K4"], "K5=", coeffs["K5"], "K6=", coeffs["K6"], "K7=", coeffs["K7"])
    print("Schwellen:")
    print("thr_clear=", coeffs["thr_clear"], "thr_light=", coeffs["thr_light"], "thr_heavy=", coeffs["thr_heavy"])
    print("")

    if not sensor_connected():
        print("Fehler: MLX90614 nicht erreichbar oder unplausible Werte")
        return

    Ta, Ts = read_mlx90614_avg()
    delta = round(Ts - Ta, 2)

    Tsky = compute_tsky_cloudwatcher(
        Ts=Ts, Ta=Ta,
        K1=coeffs["K1"], K2=coeffs["K2"], K3=coeffs["K3"], K4=coeffs["K4"],
        K5=coeffs["K5"], K6=coeffs["K6"], K7=coeffs["K7"]
    )

    pred = classify_by_thresholds(Tsky, coeffs["thr_clear"], coeffs["thr_light"], coeffs["thr_heavy"])

    print("Messwerte:")
    print("Ta Ambient :", Ta, "GradC")
    print("Ts Object  :", Ts, "GradC")
    print("Delta      :", delta, "GradC")
    print("Tsky       :", round(Tsky, 2), "GradC")
    print("")
    print("Vorhersage Wolkenstatus:", pred)

    label = prompt_label()
    if label is None:
        print("Abbruch ohne Lernen.")
        return

    # log sample with current coeffs BEFORE updating
    ts_iso = datetime.now().isoformat(timespec="seconds")
    append_sample(ts_iso, Ta, Ts, delta, Tsky, pred, label, coeffs)

    # Phase 1 update thresholds
    coeffs = update_thresholds(coeffs, pred, label)

    # Phase 2 update K1/K2 (based on recent samples)
    samples = read_samples_for_phase2(max_rows=4000)
    coeffs2, changed, msg = phase2_update_k1k2(coeffs, samples)

    # save
    save_coeffs(coeffs2)

    print("")
    print("Gespeichert in:", SAMPLES_FILE)
    print("Aktualisiert  :", COEFFS_FILE)
    print("Phase2        :", msg)
    print("")
    print("Neue Koeffizienten:")
    print("K1=", coeffs2["K1"], "K2=", coeffs2["K2"])
    print("Neue Schwellen:")
    print("thr_clear=", coeffs2["thr_clear"], "thr_light=", coeffs2["thr_light"], "thr_heavy=", coeffs2["thr_heavy"])
    print("")


if __name__ == "__main__":
    main()
