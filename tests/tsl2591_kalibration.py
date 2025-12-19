#!/usr/bin/env python3
"""
tsl2591_kalibration.py

Standalone calibration helper for TSL2591 using a nearby reference SQM value (e.g., TESS).

Key points:
- AUTO-RANGE is always enabled (based on RAW CH0/CH1).
- Prompts the user for SQM reference at startup (press Enter to skip).
- Computes SQM-like from CH0:
    SQM = sqm_const - 2.5*log10(CH0)
- If SQM_ref provided, computes per-sample calibration constant:
    C_i = SQM_ref + 2.5*log10(CH0)
  Stores to CSV and recommends sqm_const (median).

Robustness improvements:
- Retries reads when CH0/CH1 == 0/0 (invalid).
- Optional min CH0 threshold to avoid extremely noisy samples.
- If too many invalid samples in a row, re-runs auto-range.

No config, no influx. ASCII-only, English-only output.
"""

import argparse
import csv
import math
import os
import statistics
import sys
import time

# Try imports
try:
    import board
    import busio
except ImportError:
    print("ERROR: Could not import 'board' or 'busio'.")
    print("Install Adafruit Blinka:")
    print("  sudo pip3 install adafruit-blinka")
    sys.exit(1)

try:
    import adafruit_tsl2591
except ImportError:
    print("ERROR: Module 'adafruit_tsl2591' not installed.")
    print("Install with:")
    print("  sudo pip3 install adafruit-circuitpython-tsl2591")
    sys.exit(1)


def safe_float(x, fallback=None):
    try:
        if x is None:
            return fallback
        return float(x)
    except Exception:
        return fallback


def safe_value(x, fallback=0.0001):
    v = safe_float(x, None)
    if v is None or v <= 0:
        return fallback
    return v


def read_raw_counts(sensor):
    try:
        raw = sensor.raw_luminosity
        if isinstance(raw, tuple) and len(raw) >= 2:
            return int(raw[0]), int(raw[1])
    except Exception:
        pass
    return None, None


def settle_for_inucker(integration_ms: int):
    # wait slightly longer than integration time
    time.sleep(integration_ms / 1000.0 + 0.06)


def compute_sqm_from_ch0(ch0: int, sqm_const: float) -> float:
    if ch0 is None or ch0 <= 0:
        return float("nan")
    return sqm_const - 2.5 * math.log10(float(ch0))


def compute_const_from_ref(ch0: int, sqm_ref: float) -> float:
    if ch0 is None or ch0 <= 0:
        return float("nan")
    return float(sqm_ref) + 2.5 * math.log10(float(ch0))


def ensure_csv_header(path: str):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "timestamp",
            "gain",
            "exposure_ms",
            "ch0",
            "ch1",
            "lux",
            "sqm_ref",
            "const_ci",
        ])


def append_calib_row(path: str, row: dict):
    ensure_csv_header(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            row.get("timestamp", ""),
            row.get("gain", ""),
            row.get("exposure_ms", ""),
            row.get("ch0", ""),
            row.get("ch1", ""),
            row.get("lux", ""),
            row.get("sqm_ref", ""),
            row.get("const_ci", ""),
        ])


def load_consts_from_csv(path: str):
    consts = []
    if not os.path.exists(path):
        return consts
    try:
        with open(path, "r", newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                try:
                    v = float(row.get("const_ci", "") or "nan")
                    if math.isfinite(v):
                        consts.append(v)
                except Exception:
                    continue
    except Exception:
        return consts
    return consts


def set_gain_and_exposure(sensor, gain_str: str, exposure_ms: int):
    gain_map = {
        "low": adafruit_tsl2591.GAIN_LOW,
        "med": adafruit_tsl2591.GAIN_MED,
        "high": adafruit_tsl2591.GAIN_HIGH,
        "max": adafruit_tsl2591.GAIN_MAX,
    }
    it_map = {
        100: adafruit_tsl2591.INTEGRATIONTIME_100MS,
        200: adafruit_tsl2591.INTEGRATIONTIME_200MS,
        300: adafruit_tsl2591.INTEGRATIONTIME_300MS,
        400: adafruit_tsl2591.INTEGRATIONTIME_400MS,
        500: adafruit_tsl2591.INTEGRATIONTIME_500MS,
        600: adafruit_tsl2591.INTEGRATIONTIME_600MS,
    }
    sensor.gain = gain_map[gain_str]
    sensor.integration_time = it_map[exposure_ms]


def get_current_settings(sensor):
    g = None
    it = None
    try:
        g = sensor.gain
    except Exception:
        pass
    try:
        it = sensor.integration_time
    except Exception:
        pass
    return g, it


def auto_range(sensor, verbose: bool = False):
    gain_factors = {"low": 1, "med": 25, "high": 428, "max": 9876}
    gains = ["low", "med", "high", "max"]
    exposures = [100, 200, 300, 400, 500, 600]

    combos = []
    for g in gains:
        for e in exposures:
            combos.append((gain_factors[g] * e, g, e))
    combos.sort(key=lambda x: x[0])

    TARGET_LOW = 2000
    TARGET_HIGH = 45000
    SAT_THRESHOLD = 65000

    best = None
    best_score = None

    if verbose:
        print("Auto-range: scanning gain/exposure combinations...")

    for _, g, e in combos:
        try:
            set_gain_and_exposure(sensor, g, e)
        except Exception as ex:
            if verbose:
                print(f"  skip gain={g} exp={e}ms (set failed): {ex}")
            continue

        settle_for_integration(e)
        ch0, ch1 = read_raw_counts(sensor)

        if ch0 is None:
            if verbose:
                print(f"  gain={g:4s} exp={e:3d}ms  RAW not available -> using this setting")
            return g, e

        # Treat 0/0 as invalid, not "too dark"
        if ch0 == 0 and ch1 == 0:
            if verbose:
                print(f"  gain={g:4s} exp={e:3d}ms  CH0/CH1=0/0 INVALID")
            continue

        saturated = (ch0 >= SAT_THRESHOLD) or (ch1 >= SAT_THRESHOLD)
        too_dark = (ch0 < TARGET_LOW)
        in_window = (TARGET_LOW <= ch0 <= TARGET_HIGH) and not saturated

        if verbose:
            flags = []
            if saturated:
                flags.append("SAT")
            if too_dark:
                flags.append("DARK")
            if in_window:
                flags.append("OK")
            print(f"  gain={g:4s} exp={e:3d}ms  CH0={ch0:5d} CH1={ch1:5d}  {' '.join(flags)}")

        if in_window:
            return g, e

        if saturated:
            score = -10_000_000 - ch0
        else:
            if ch0 <= TARGET_HIGH:
                score = ch0
            else:
                score = TARGET_HIGH - (ch0 - TARGET_HIGH)

        if best_score is None or score > best_score:
            best_score = score
            best = (g, e)

    if best is None:
        return "med", 200
    return best


def read_valid_raw(sensor, exposure_ms: int, read_retries: int, retry_delay: float, min_ch0: int):
    """
    Returns (ch0, ch1) or (None, None) after retries.
    Filters:
      - invalid 0/0
      - optional min_ch0 threshold
    """
    for _ in range(max(1, read_retries)):
        ch0, ch1 = read_raw_counts(sensor)
        if ch0 is None:
            return None, None
        if ch0 == 0 and ch1 == 0:
            time.sleep(retry_delay)
            settle_for_integration(exposure_ms)
            continue
        if min_ch0 > 0 and ch0 < min_ch0:
            # Treat extremely low counts as unstable/noisy (optional)
            time.sleep(retry_delay)
            settle_for_integration(exposure_ms)
            continue
        return ch0, ch1
    return None, None


def prompt_sqm_ref():
    try:
        s = input("Enter SQM reference from TESS (mag/arcsec^2) or press Enter to skip: ").strip()
    except EOFError:
        return None
    if not s:
        return None
    s = s.replace(",", ".")
    v = safe_float(s, None)
    if v is None:
        print("WARNING: Invalid SQM reference input. Skipping calibration.")
        return None
    if v < 10 or v > 25:
        print("WARNING: SQM ref value looks unusual (expected roughly 14..22 at night). Using it anyway.")
    return v


def parse_args():
    p = argparse.ArgumentParser(description="TSL2591 calibration (auto-range + prompt + robust reads).")
    p.add_argument("--samples", type=int, default=10, help="Number of samples to record (default: 10)")
    p.add_argument("--interval", type=float, default=2.0, help="Seconds between samples (default: 2.0)")
    p.add_argument("--sqm-const", type=float, default=22.0, help="Starting SQM constant C (default: 22.0)")
    p.add_argument("--calib-file", default="tsl2591_calibration_samples.csv",
                   help="CSV file to store calibration samples")
    p.add_argument("--auto-verbose", action="store_true", help="Print auto-range scan details")
    p.add_argument("--read-retries", type=int, default=5, help="Retries for invalid reads (default: 5)")
    p.add_argument("--read-retry-delay", type=float, default=0.15, help="Delay between read retries (default: 0.15s)")
    p.add_argument("--min-ch0", type=int, default=50, help="Minimum CH0 to accept as valid (default: 50; set 0 to disable)")
    p.add_argument("--rerange-after-invalid", type=int, default=3,
                   help="Re-run auto-range after N invalid samples in a row (default: 3)")
    return p.parse_args()


def main():
    args = parse_args()

    print("=== TSL2591 Calibration Test ===")
    print("Interface: I2C (SCL/SDA)")
    print("Mode: auto-range always enabled")
    print(f"Samples: {args.samples}, interval: {args.interval}s")
    print(f"Starting SQM constant: {args.sqm_const:.2f}")
    print(f"Calibration CSV: {args.calib_file}")
    print(f"Read retries: {args.read_retries}, min_ch0: {args.min_ch0}, rerange_after_invalid: {args.rerange_after_invalid}")
    print()

    sqm_ref = prompt_sqm_ref()
    if sqm_ref is not None:
        print(f"Calibration enabled: SQM_ref={sqm_ref:.2f}")
    else:
        print("Calibration disabled (no SQM_ref provided).")
    print()

    # Open I2C
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
    except Exception as e:
        print("ERROR: Could not open I2C interface.")
        print("Hint: enable I2C using 'sudo raspi-config'.")
        print("Exception:", e)
        sys.exit(1)

    # Init sensor
    try:
        sensor = adafruit_tsl2591.TSL2591(i2c)
    except Exception as e:
        print("ERROR: Could not initialize TSL2591 sensor.")
        print("Hint: run 'i2cdetect -y 1' and look for '29'.")
        print("Exception:", e)
        sys.exit(1)

    # Initial auto-range selection
    gain_sel, exp_sel = auto_range(sensor, verbose=args.auto_verbose)
    print(f"Auto-range selected: gain={gain_sel}, exposure={exp_sel}ms")
    try:
        set_gain_and_exposure(sensor, gain_sel, exp_sel)
    except Exception as ex:
        print("ERROR: Could not apply auto-range settings:", ex)
        sys.exit(1)

    settle_for_integration(exp_sel)
    g_now, it_now = get_current_settings(sensor)
    print(f"Active settings: gain={g_now}, integration_time={it_now}")
    print()

    existing_consts = load_consts_from_csv(args.calib_file) if sqm_ref is not None else []
    new_consts = []

    invalid_streak = 0

    for i in range(args.samples):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # read lux (info) + robust raw
        try:
            lux = safe_value(sensor.lux)
            ch0, ch1 = read_valid_raw(sensor, exp_sel, args.read_retries, args.read_retry_delay, args.min_ch0)
        except Exception as e:
            print("ERROR: Failed to read sensor:", e)
            break

        print(f"[{timestamp}] Sample {i+1}/{args.samples}")

        if ch0 is None:
            invalid_streak += 1
            print("  Raw CH0/CH1 : invalid (0/0 or too low after retries)")
            print(f"  Lux         : {lux:.3f} lx (info)")
            print()

            if args.rerange_after_invalid > 0 and invalid_streak >= args.rerange_after_invalid:
                print("  Action      : too many invalid reads -> re-running auto-range ...")
                gain_sel, exp_sel = auto_range(sensor, verbose=args.auto_verbose)
                print(f"  New range    : gain={gain_sel}, exposure={exp_sel}ms")
                try:
                    set_gain_and_exposure(sensor, gain_sel, exp_sel)
                except Exception as ex:
                    print("ERROR: Could not apply new auto-range settings:", ex)
                    break
                settle_for_integration(exp_sel)
                invalid_streak = 0
                print()
            time.sleep(max(0.0, args.interval))
            continue

        invalid_streak = 0

        sat = (ch0 >= 65000) or (ch1 >= 65000)
        sqm_pred = compute_sqm_from_ch0(ch0, args.sqm_const)

        print(f"  Raw CH0/CH1 : {ch0}/{ch1}" + ("  (SATURATED)" if sat else ""))
        print(f"  SQM (CH0)   : {sqm_pred:.2f} mag/arcsec^2   (using C={args.sqm_const:.2f})")
        print(f"  Lux         : {lux:.3f} lx (info)")

        if sqm_ref is not None and (not sat) and ch0 > 0:
            ci = compute_const_from_ref(ch0, sqm_ref)
            if math.isfinite(ci):
                new_consts.append(ci)
                append_calib_row(args.calib_file, {
                    "timestamp": timestamp,
                    "gain": gain_sel,
                    "exposure_ms": exp_sel,
                    "ch0": ch0,
                    "ch1": ch1,
                    "lux": f"{lux:.6f}",
                    "sqm_ref": f"{sqm_ref:.3f}",
                    "const_ci": f"{ci:.6f}",
                })
                print(f"  Calib C_i   : {ci:.4f}")
        print()
        time.sleep(max(0.0, args.interval))

    if sqm_ref is not None:
        all_consts = existing_consts + new_consts
        print("=== Calibration Summary ===")
        if len(all_consts) == 0:
            print("No usable calibration samples recorded.")
        else:
            med = statistics.median(all_consts)
            stdev = statistics.pstdev(all_consts) if len(all_consts) >= 2 else float("nan")
            print(f"Usable samples total: {len(all_consts)}")
            print(f"Recommended sqm_const (median): {med:.4f}")
            if math.isfinite(stdev):
                print(f"Spread (population stdev): {stdev:.4f}")
            print(f"Test with: python3 tsl2591_kalibration.py --sqm-const {med:.4f}")
            print(f"Later config: TSL2591_SQM_CONSTANT = {med:.4f}")

    print("\nTSL2591 calibration test finished.")


if __name__ == "__main__":
    main()
