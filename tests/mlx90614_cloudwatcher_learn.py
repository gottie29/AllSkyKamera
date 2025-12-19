#!/usr/bin/env python3
"""
MLX90614 CloudWatcher Standalone mit Online-Learning (ASCII only)

- Keine Sonderzeichen (ASCII only)
- Kein askutils
- Kein config.py
- Kein Influx
- Ausgabe nur auf Konsole

Phase 1:
- Schwellenwerte thr_clear/thr_light/thr_heavy werden nach jedem Lauf leicht angepasst

Phase 2:
- Wenn genug Samples vorhanden sind, werden K1 und K2 minimal angepasst
- K3..K7 bleiben unveraendert
- Grenzen und kleine Lernrate fuer Stabilitaet

Neu:
- Automatisches Anlegen von mlx90614_coeffs.json mit Default-Werten, falls Datei fehlt
- Logging nach mlx90614_samples.csv
- Quality Report (Samples, Klassenverteilung, Ta-Spanne, Rolling Accuracy, Ampel)
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

# -------------------------------------------------
# Files
# -------------------------------------------------
COEFFS_FILE = "mlx90614_coeffs.json"
SAMPLES_FILE = "mlx90614_samples.csv"

# -------------------------------------------------
# I2C defaults
# -------------------------------------------------
I2C_BUS = 1
I2C_ADDR = 0x5A

REG_TA = 0x06
REG_TOBJ1 = 0x07

_bus = None

# -------------------------------------------------
# Default coeffs (used when coeff file does not exist)
# -------------------------------------------------
DEFAULT_COEFFS = {
    "K1": 100.0,
    "K2": 0.0,
    "K3": 0.0,
    "K4": 0.0,
    "K5": 0.0,
    "K6": 0.0,
    "K7": 0.0,

    "thr_clear": -25.0,
    "thr_light": -18.0,
    "thr_heavy": -12.0,

    "learn_rate_thr": 0.15,

    "phase2_enabled": True,
    "min_samples_k": 80,
    "learn_rate_k": 0.02,

    "k1_min": 50.0,
    "k1_max": 150.0,
    "k2_min": -400.0,
    "k2_max": 400.0,

    "target_tsky_clear": -30.0,
    "target_tsky_light": -21.0,
    "target_tsky_heavy": -15.0,
    "target_tsky_overcast": -6.0,

    "quality_min_samples_thr": 80,
    "quality_min_samples_k": 250,
    "quality_min_acc50_thr": 0.75,
    "quality_min_acc200_thr": 0.70,
    "quality_min_acc50_k": 0.80,
    "quality_min_acc200_k": 0.75,
    "quality_min_ta_range_thr": 6.0,
    "quality_min_ta_range_k": 12.0,
    "quality_min_class_count": 10
}


# -------------------------------------------------
# Helpers: clamp, ordering
# -------------------------------------------------
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


# -------------------------------------------------
# Coeffs file bootstrap/load/save
# -------------------------------------------------
def ensure_coeffs_file():
    """
    Ensure mlx90614_coeffs.json exists.
    If missing, create it using DEFAULT_COEFFS.
    """
    if os.path.exists(COEFFS_FILE):
        return

    print("Info: coeffs file missing, creating default:", COEFFS_FILE)
    with open(COEFFS_FILE, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_COEFFS, f, indent=2, sort_keys=True)


def load_coeffs():
    ensure_coeffs_file()

    with open(COEFFS_FILE, "r", encoding="utf-8") as f:
        c = json.load(f)

    # Upgrade-safe: add missing keys
    for k, v in DEFAULT_COEFFS.items():
        c.setdefault(k, v)

    c = enforce_threshold_order(c)
    return c


def save_coeffs(c):
    c = enforce_threshold_order(c)

    # clamp K1/K2 to bounds
    c["K1"] = clamp(float(c["K1"]), float(c["k1_min"]), float(c["k1_max"]))
    c["K2"] = clamp(float(c["K2"]), float(c["k2_min"]), float(c["k2_max"]))

    with open(COEFFS_FILE, "w", encoding="utf-8") as f:
        json.dump(c, f, indent=2, sort_keys=True)


# -------------------------------------------------
# MLX90614 low-level
# -------------------------------------------------
def get_bus():
    global _bus
    if _bus is None:
        if smbus is None:
            raise RuntimeError("python3-smbus not installed. sudo apt install python3-smbus i2c-tools")
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

    # plausibility + byte swap fallback
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


# -------------------------------------------------
# CloudWatcher model
# -------------------------------------------------
def sgn(x: float) -> int:
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


def compute_tsky_cloudwatcher(Ts, Ta, K1, K2, K3, K4, K5, K6, K7) -> float:
    T0 = K2 / 10.0
    d = abs(T0 - Ta)

    # T67 term
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
    # 0=clear, 1=light, 2=heavy, 3=overcast
    if Tsky <= thr_clear:
        return 0
    if Tsky <= thr_light:
        return 1
    if Tsky <= thr_heavy:
        return 2
    return 3


# -------------------------------------------------
# Logging
# -------------------------------------------------
def append_sample(ts_iso, Ta, Ts, delta, Tsky, pred, label, coeffs):
    file_exists = os.path.exists(SAMPLES_FILE)
    with open(SAMPLES_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not file_exists:
            w.writerow([
                "timestamp_iso", "Ta_GradC", "Ts_GradC", "Delta_GradC", "Tsky_GradC",
                "pred", "label",
                "K1", "K2", "K3", "K4", "K5", "K6", "K7",
                "thr_clear", "thr_light", "thr_heavy"
            ])
        w.writerow([
            ts_iso, Ta, Ts, delta, round(Tsky, 4),
            pred, label,
            coeffs["K1"], coeffs["K2"], coeffs["K3"], coeffs["K4"], coeffs["K5"], coeffs["K6"], coeffs["K7"],
            coeffs["thr_clear"], coeffs["thr_light"], coeffs["thr_heavy"]
        ])


def read_samples(max_rows=4000):
    if not os.path.exists(SAMPLES_FILE):
        return []

    rows = []
    with open(SAMPLES_FILE, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                Ta = float(row["Ta_GradC"])
                Ts = float(row["Ts_GradC"])
                label = int(row["label"])
                pred = int(row["pred"])
                rows.append((Ta, Ts, label, pred))
            except Exception:
                pass

    if len(rows) > max_rows:
        rows = rows[-max_rows:]
    return rows


# -------------------------------------------------
# Phase 1: thresholds update
# -------------------------------------------------
def update_thresholds(coeffs, pred, label):
    lr = float(coeffs.get("learn_rate_thr", 0.15))

    thr_clear = float(coeffs["thr_clear"])
    thr_light = float(coeffs["thr_light"])
    thr_heavy = float(coeffs["thr_heavy"])

    if pred == label:
        return coeffs

    # pred<label => too clear => shift thresholds up
    # pred>label => too cloudy => shift thresholds down
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


# -------------------------------------------------
# Phase 2: learn K1/K2
# -------------------------------------------------
def label_to_target(coeffs, label):
    if label == 0:
        return float(coeffs["target_tsky_clear"])
    if label == 1:
        return float(coeffs["target_tsky_light"])
    if label == 2:
        return float(coeffs["target_tsky_heavy"])
    return float(coeffs["target_tsky_overcast"])


def loss_mse(coeffs, samples, K1, K2):
    K3 = float(coeffs["K3"])
    K4 = float(coeffs["K4"])
    K5 = float(coeffs["K5"])
    K6 = float(coeffs["K6"])
    K7 = float(coeffs["K7"])

    if not samples:
        return 0.0

    s = 0.0
    n = 0
    for (Ta, Ts, label, _pred) in samples:
        tsky = compute_tsky_cloudwatcher(Ts, Ta, K1, K2, K3, K4, K5, K6, K7)
        target = label_to_target(coeffs, label)
        e = (tsky - target)
        s += e * e
        n += 1
    return s / float(n)


def phase2_update_k1k2(coeffs, samples):
    if not coeffs.get("phase2_enabled", True):
        return coeffs, False, "Phase2 disabled"

    min_samples = int(coeffs.get("min_samples_k", 80))
    if len(samples) < min_samples:
        return coeffs, False, "Not enough samples for Phase2"

    lr = float(coeffs.get("learn_rate_k", 0.02))

    k1 = float(coeffs["K1"])
    k2 = float(coeffs["K2"])

    k1_min = float(coeffs["k1_min"])
    k1_max = float(coeffs["k1_max"])
    k2_min = float(coeffs["k2_min"])
    k2_max = float(coeffs["k2_max"])

    eps_k1 = 0.25
    eps_k2 = 1.0

    base = loss_mse(coeffs, samples, k1, k2)

    l1p = loss_mse(coeffs, samples, clamp(k1 + eps_k1, k1_min, k1_max), k2)
    l1m = loss_mse(coeffs, samples, clamp(k1 - eps_k1, k1_min, k1_max), k2)
    g1 = (l1p - l1m) / (2.0 * eps_k1)

    l2p = loss_mse(coeffs, samples, k1, clamp(k2 + eps_k2, k2_min, k2_max))
    l2m = loss_mse(coeffs, samples, k1, clamp(k2 - eps_k2, k2_min, k2_max))
    g2 = (l2p - l2m) / (2.0 * eps_k2)

    new_k1 = clamp(k1 - lr * g1, k1_min, k1_max)
    new_k2 = clamp(k2 - lr * g2, k2_min, k2_max)

    new_loss = loss_mse(coeffs, samples, new_k1, new_k2)

    if new_loss <= base:
        coeffs["K1"] = float(new_k1)
        coeffs["K2"] = float(new_k2)
        return coeffs, True, "Phase2 updated (loss improved)"
    else:
        return coeffs, False, "Phase2 skipped (no improvement)"


# -------------------------------------------------
# Quality report
# -------------------------------------------------
def rolling_accuracy(samples, last_n):
    if not samples:
        return None
    n = min(last_n, len(samples))
    if n <= 0:
        return None
    sub = samples[-n:]
    ok = 0
    for (_Ta, _Ts, label, pred) in sub:
        if label == pred:
            ok += 1
    return ok / float(n)


def class_counts(samples):
    c = {0: 0, 1: 0, 2: 0, 3: 0}
    for (_Ta, _Ts, label, _pred) in samples:
        if label in c:
            c[label] += 1
    return c


def ta_range(samples):
    if not samples:
        return None
    tas = [x[0] for x in samples]
    return (min(tas), max(tas), max(tas) - min(tas))


def balance_score(counts):
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    ideal = total / 4.0
    dev = 0.0
    for k in (0, 1, 2, 3):
        dev += abs(counts[k] - ideal)
    score = 1.0 - (dev / (2.0 * total))
    if score < 0.0:
        score = 0.0
    return score


def amp(ok):
    return "GREEN" if ok else "YELLOW"


def quality_report(coeffs, samples):
    total = len(samples)
    cnt = class_counts(samples)
    acc50 = rolling_accuracy(samples, 50)
    acc200 = rolling_accuracy(samples, 200)
    tr = ta_range(samples)
    bal = balance_score(cnt)

    print("")
    print("Quality Report")
    print("Samples total:", total)
    print("Samples per class: c0=", cnt[0], "c1=", cnt[1], "c2=", cnt[2], "c3=", cnt[3])

    if tr is None:
        print("Ta range: n/a")
        ta_span = 0.0
    else:
        ta_span = tr[2]
        print("Ta min:", round(tr[0], 2), "Ta max:", round(tr[1], 2), "Ta span:", round(ta_span, 2), "GradC")

    if acc50 is not None:
        print("Rolling accuracy last50 :", round(acc50, 3))
    else:
        print("Rolling accuracy last50 : n/a")

    if acc200 is not None:
        print("Rolling accuracy last200:", round(acc200, 3))
    else:
        print("Rolling accuracy last200: n/a")

    print("Label balance score (0..1):", round(bal, 3))

    min_samples_thr = int(coeffs["quality_min_samples_thr"])
    min_acc50_thr = float(coeffs["quality_min_acc50_thr"])
    min_acc200_thr = float(coeffs["quality_min_acc200_thr"])
    min_ta_span_thr = float(coeffs["quality_min_ta_range_thr"])
    min_class_count = int(coeffs["quality_min_class_count"])

    classes_with_enough = sum(1 for k in (0, 1, 2, 3) if cnt[k] >= min_class_count)

    ok_thr = True
    if total < min_samples_thr:
        ok_thr = False
    if acc50 is None or acc50 < min_acc50_thr:
        ok_thr = False
    if acc200 is None or acc200 < min_acc200_thr:
        ok_thr = False
    if ta_span < min_ta_span_thr:
        ok_thr = False
    if classes_with_enough < 2:
        ok_thr = False

    min_samples_k = int(coeffs["quality_min_samples_k"])
    min_acc50_k = float(coeffs["quality_min_acc50_k"])
    min_acc200_k = float(coeffs["quality_min_acc200_k"])
    min_ta_span_k = float(coeffs["quality_min_ta_range_k"])

    ok_k = True
    if total < min_samples_k:
        ok_k = False
    if acc50 is None or acc50 < min_acc50_k:
        ok_k = False
    if acc200 is None or acc200 < min_acc200_k:
        ok_k = False
    if ta_span < min_ta_span_k:
        ok_k = False
    if classes_with_enough < 3:
        ok_k = False

    print("")
    print("Readiness")
    print("Thresholds (Phase1) :", amp(ok_thr))
    print("K1/K2 (Phase2)      :", amp(ok_k))
    print("")

    if not ok_thr:
        print("Hints for Thresholds:")
        if total < min_samples_thr:
            print("- Need more samples. Target:", min_samples_thr)
        if ta_span < min_ta_span_thr:
            print("- Need more Ta variety. Target span:", min_ta_span_thr, "GradC")
        if acc50 is None or acc50 < min_acc50_thr:
            print("- Improve recent accuracy (last50). Target:", min_acc50_thr)
        if acc200 is None or acc200 < min_acc200_thr:
            print("- Improve longer accuracy (last200). Target:", min_acc200_thr)
        if classes_with_enough < 2:
            print("- Need labels from at least 2 classes, each >= ", min_class_count)
        print("")

    if ok_thr and not ok_k:
        print("Hints for K1/K2:")
        if total < min_samples_k:
            print("- Need more samples. Target:", min_samples_k)
        if ta_span < min_ta_span_k:
            print("- Need more Ta variety. Target span:", min_ta_span_k, "GradC")
        if acc50 is None or acc50 < min_acc50_k:
            print("- Improve recent accuracy (last50). Target:", min_acc50_k)
        if acc200 is None or acc200 < min_acc200_k:
            print("- Improve longer accuracy (last200). Target:", min_acc200_k)
        if classes_with_enough < 3:
            print("- Need labels from at least 3 classes, each >= ", min_class_count)
        print("")

    if ok_k:
        print("Status: K1/K2 look stable enough for this dataset.")
        print("Note: Seasonal changes may require more samples over time.")
        print("")


# -------------------------------------------------
# User prompt
# -------------------------------------------------
def prompt_label():
    print("")
    print("Please enter true cloud status:")
    print("0 = clear")
    print("1 = light clouds")
    print("2 = heavy clouds")
    print("3 = overcast")
    while True:
        s = input("Your label (0-3, or Enter to abort): ").strip()
        if s == "":
            return None
        if s in ("0", "1", "2", "3"):
            return int(s)
        print("Invalid input. Enter 0-3 or Enter.")


def main():
    coeffs = load_coeffs()

    # show quality report first
    samples = read_samples(max_rows=4000)
    quality_report(coeffs, samples)

    print("Current Model")
    print("K1=", coeffs["K1"], "K2=", coeffs["K2"], "K3=", coeffs["K3"],
          "K4=", coeffs["K4"], "K5=", coeffs["K5"], "K6=", coeffs["K6"], "K7=", coeffs["K7"])
    print("thr_clear=", coeffs["thr_clear"], "thr_light=", coeffs["thr_light"], "thr_heavy=", coeffs["thr_heavy"])
    print("")

    if not sensor_connected():
        print("Error: MLX90614 not reachable or implausible values")
        return

    Ta, Ts = read_mlx90614_avg()
    delta = round(Ts - Ta, 2)

    Tsky = compute_tsky_cloudwatcher(
        Ts=Ts, Ta=Ta,
        K1=coeffs["K1"], K2=coeffs["K2"], K3=coeffs["K3"], K4=coeffs["K4"],
        K5=coeffs["K5"], K6=coeffs["K6"], K7=coeffs["K7"]
    )

    pred = classify_by_thresholds(Tsky, coeffs["thr_clear"], coeffs["thr_light"], coeffs["thr_heavy"])

    print("Measurement")
    print("Ta Ambient :", Ta, "GradC")
    print("Ts Object  :", Ts, "GradC")
    print("Delta      :", delta, "GradC")
    print("Tsky       :", round(Tsky, 2), "GradC")
    print("Prediction :", pred)

    label = prompt_label()
    if label is None:
        print("Abort without learning.")
        return

    ts_iso = datetime.now().isoformat(timespec="seconds")
    append_sample(ts_iso, Ta, Ts, delta, Tsky, pred, label, coeffs)

    # Phase 1 update thresholds
    coeffs = update_thresholds(coeffs, pred, label)

    # Phase 2 update K1/K2
    samples2 = read_samples(max_rows=4000)
    coeffs2, _changed, msg = phase2_update_k1k2(coeffs, samples2)
    save_coeffs(coeffs2)

    print("")
    print("Saved:", SAMPLES_FILE)
    print("Updated:", COEFFS_FILE)
    print("Phase2:", msg)
    print("New K1/K2:", coeffs2["K1"], coeffs2["K2"])
    print("New thresholds:", coeffs2["thr_clear"], coeffs2["thr_light"], coeffs2["thr_heavy"])
    print("")


if __name__ == "__main__":
    main()
