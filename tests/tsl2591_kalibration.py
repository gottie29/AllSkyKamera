#!/usr/bin/env python3
"""
tsl2591_kalibration.py (robust)

Standalone calibration helper for TSL2591 using a nearby SQM reference (e.g., TESS).

Core:
- Auto-range is always enabled (night-aware).
- Prompts for SQM reference at startup (press Enter to skip calibration).
- SQM model from RAW CH0:
    SQM = sqm_const - 2.5*log10(CH0)
- If SQM_ref is provided:
    C_i = SQM_ref + 2.5*log10(CH0)
  Store calibration samples in CSV and recommend sqm_const (median).

Robustness:
- 0/0 reads are treated as INVALID and ignored.
- Warmup after range changes (discard N reads).
- Sensor reset after many invalid reads (re-init sensor; optional re-init I2C).
- Auto-range chooses settings that give VALID reads and CH0 in a target window.

Portability:
- Works with both Adafruit API styles:
  - newer enum API (Gain, IntegrationTime)
  - older constants API (GAIN_LOW, INTEGRATIONTIME_100MS, ...)

No config, no influx. ASCII-only, English-only output.
"""

import argparse
import csv
import math
import os
import statistics
import sys
import time

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

# -----------------------------
# Adafruit API compatibility
# -----------------------------
# Newer libraries export: TSL2591, Gain, IntegrationTime
# Older libraries use: GAIN_* and INTEGRATIONTIME_* constants
try:
    from adafruit_tsl2591 import Gain as _Gain, IntegrationTime as _IntegrationTime  # type: ignore
    _API_STYLE = "enum"
except Exception:
    _Gain = None
    _IntegrationTime = None
    _API_STYLE = "const"


def _resolve_gain_value(gain_str: str):
    g = gain_str.strip().lower()
    if _API_STYLE == "enum" and _Gain is not None:
        return {
            "low": _Gain.LOW,
            "med": _Gain.MED,
            "high": _Gain.HIGH,
            "max": _Gain.MAX,
        }[g]
    # constants style
    return {
        "low": adafruit_tsl2591.GAIN_LOW,
        "med": adafruit_tsl2591.GAIN_MED,
        "high": adafruit_tsl2591.GAIN_HIGH,
        "max": adafruit_tsl2591.GAIN_MAX,
    }[g]


def _resolve_integration_value(exposure_ms: int):
    if _API_STYLE == "enum" and _IntegrationTime is not None:
        return {
            100: _IntegrationTime.TIME_100MS,
            200: _IntegrationTime.TIME_200MS,
            300: _IntegrationTime.TIME_300MS,
            400: _IntegrationTime.TIME_400MS,
            500: _IntegrationTime.TIME_500MS,
            600: _IntegrationTime.TIME_600MS,
        }[exposure_ms]
    # constants style
    return {
        100: adafruit_tsl2591.INTEGRATIONTIME_100MS,
        200: adafruit_tsl2591.INTEGRATIONTIME_200MS,
        300: adafruit_tsl2591.INTEGRATIONTIME_300MS,
        400: adafruit_tsl2591.INTEGRATIONTIME_400MS,
        500: adafruit_tsl2591.INTEGRATIONTIME_500MS,
        600: adafruit_tsl2591.INTEGRATIONTIME_600MS,
    }[exposure_ms]


# -----------------------------
# Small utilities
# -----------------------------
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


def ts_now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def settle_for_integration(integration_ms: int):
    # slightly longer than integration time
    time.sleep(integration_ms / 1000.0 + 0.08)


def compute_sqm_from_ch0(ch0: int, sqm_const: float) -> float:
    if ch0 is None or ch0 <= 0:
        return float("nan")
    return sqm_const - 2.5 * math.log10(float(ch0))


def compute_const_from_ref(ch0: int, sqm_ref: float) -> float:
    if ch0 is None or ch0 <= 0:
        return float("nan")
    return float(sqm_ref) + 2.5 * math.log10(float(ch0))


# -----------------------------
# CSV handling
# -----------------------------
CSV_FIELDS = [
    "timestamp",
    "gain",
    "exposure_ms",
    "ch0",
    "ch1",
    "lux",
    "sqm_ref",
    "const_ci",
    "valid",
    "note",
]


def ensure_csv_header(path: str):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_FIELDS)


def append_csv(path: str, row: dict):
    ensure_csv_header(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([row.get(k, "") for k in CSV_FIELDS])


def load_all_time_consts(path: str):
    consts = []
    if not os.path.exists(path):
        return consts
    try:
        with open(path, "r", newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                try:
                    if str(row.get("valid", "")).strip().lower() not in ("1", "true", "yes"):
                        continue
                    v = float(row.get("const_ci", "") or "nan")
                    if math.isfinite(v):
                        consts.append(v)
                except Exception:
                    continue
    except Exception:
        return consts
    return consts


# -----------------------------
# Sensor read + settings
# -----------------------------
def read_raw_counts(sensor):
    try:
        raw = sensor.raw_luminosity
        if isinstance(raw, tuple) and len(raw) >= 2:
            return int(raw[0]), int(raw[1])
    except Exception:
        pass
    return None, None


def set_gain_and_exposure(sensor, gain_str: str, exposure_ms: int):
    sensor.gain = _resolve_gain_value(gain_str)
    sensor.integration_time = _resolve_integration_value(exposure_ms)


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


def warmup(sensor, exposure_ms: int, warmup_reads: int):
    # discard first N reads after changing settings
    for _ in range(max(0, warmup_reads)):
        settle_for_integration(exposure_ms)
        _ = read_raw_counts(sensor)


def read_valid_raw(sensor, exposure_ms: int, read_retries: int, retry_delay: float,
                   min_ch0: int, sat_threshold: int):
    """
    Returns (ch0, ch1, note) or (None, None, note) after retries.
    Invalid:
      - raw missing
      - 0/0
      - saturated
      - ch0 < min_ch0 (optional)
    """
    last_note = "invalid"
    for _ in range(max(1, read_retries)):
        ch0, ch1 = read_raw_counts(sensor)
        if ch0 is None:
            return None, None, "raw_missing"

        if ch0 == 0 and ch1 == 0:
            last_note = "zero_read"
            time.sleep(retry_delay)
            settle_for_integration(exposure_ms)
            continue

        if ch0 >= sat_threshold or ch1 >= sat_threshold:
            return None, None, "saturated"

        if min_ch0 > 0 and ch0 < min_ch0:
            last_note = "too_low"
            time.sleep(retry_delay)
            settle_for_integration(exposure_ms)
            continue

        return ch0, ch1, "ok"

    return None, None, last_note


# -----------------------------
# Night-aware auto-range
# -----------------------------
def auto_range_night(sensor, verbose: bool, sat_threshold: int,
                     target_low: int, target_high: int,
                     min_ch0_for_valid: int,
                     warmup_reads: int):
    """
    Choose gain/exposure with these goals:
    1) Must produce VALID reads (not 0/0, not saturated, ch0 >= min_ch0_for_valid)
    2) Prefer CH0 within [target_low, target_high]
    3) Otherwise choose the highest CH0 below target_high (best SNR), or the closest.

    IMPORTANT CHANGE:
    - We validate using read_valid_raw (small retry count) instead of a single raw read.

    Returns (gain_str, exposure_ms).
    """
    gain_factors = {"low": 1, "med": 25, "high": 428, "max": 9876}
    gains = ["low", "med", "high", "max"]
    exposures = [100, 200, 300, 400, 500, 600]

    combos = []
    for g in gains:
        for e in exposures:
            combos.append((gain_factors[g] * e, g, e))

    # high sensitivity first (good for dark nights)
    combos.sort(key=lambda x: x[0], reverse=True)

    best = None
    best_score = None

    if verbose:
        print("Auto-range (night): scanning gain/exposure combinations (high -> low sensitivity)...")
        print(f"  Target CH0 window: {target_low}..{target_high} (sat>={sat_threshold}, valid if CH0>={min_ch0_for_valid})")

    for _, g, e in combos:
        try:
            set_gain_and_exposure(sensor, g, e)
        except Exception as ex:
            if verbose:
                print(f"  skip gain={g} exp={e}ms (set failed): {ex}")
            continue

        warmup(sensor, e, warmup_reads)

        # validate with a short retry loop (more robust than a single read)
        ch0, ch1, note = read_valid_raw(
            sensor=sensor,
            exposure_ms=e,
            read_retries=2,
            retry_delay=0.10,
            min_ch0=min_ch0_for_valid,
            sat_threshold=sat_threshold,
        )

        if ch0 is None:
            if verbose:
                print(f"  gain={g:4s} exp={e:3d}ms  INVALID ({note})")
            continue

        in_window = (target_low <= ch0 <= target_high)
        if verbose:
            print(f"  gain={g:4s} exp={e:3d}ms  CH0={ch0:5d} CH1={ch1:5d}  {'OK' if in_window else 'VALID'}")

        if in_window:
            return g, e

        # scoring: prefer CH0 close to target_high but not above it
        if ch0 <= target_high:
            score = ch0  # maximize counts for SNR
        else:
            score = target_high - (ch0 - target_high)  # penalize above target

        if best_score is None or score > best_score:
            best_score = score
            best = (g, e)

    if best is not None:
        return best

    return "max", 600


# -----------------------------
# Prompt + CLI
# -----------------------------
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
    p = argparse.ArgumentParser(description="TSL2591 calibration (robust, night-aware auto-range).")

    p.add_argument("--samples", type=int, default=10, help="Number of samples (default: 10)")
    p.add_argument("--interval", type=float, default=2.0, help="Seconds between samples (default: 2.0)")
    p.add_argument("--sqm-const", type=float, default=22.0, help="Starting SQM constant C (default: 22.0)")
    p.add_argument("--calib-file", default="tsl2591_calibration_samples.csv", help="CSV file for calibration samples")

    # Read robustness (IMPORTANT DEFAULT CHANGE: min-ch0 now 5 for night operation)
    p.add_argument("--read-retries", type=int, default=6, help="Retries for invalid reads (default: 6)")
    p.add_argument("--read-retry-delay", type=float, default=0.20, help="Delay between retries (default: 0.20s)")
    p.add_argument("--min-ch0", type=int, default=5, help="Min CH0 to accept in normal sampling (default: 5; 0 disables)")
    p.add_argument("--sat-threshold", type=int, default=65000, help="Saturation threshold (default: 65000)")

    # Auto-range (night) (IMPORTANT DEFAULT CHANGES)
    p.add_argument("--target-ch0-low", type=int, default=10, help="Auto-range target CH0 low (default: 10)")
    p.add_argument("--target-ch0-high", type=int, default=8000, help="Auto-range target CH0 high (default: 8000)")
    p.add_argument("--min-ch0-valid", type=int, default=5, help="Minimum CH0 for a setting to be considered VALID in auto-range (default: 5)")
    p.add_argument("--warmup-reads", type=int, default=2, help="Discard N reads after changing settings (default: 2)")

    # Resets / re-range policy
    p.add_argument("--rerange-after-invalid", type=int, default=3, help="Re-run auto-range after N invalid samples in a row (default: 3)")
    p.add_argument("--reset-after-invalid", type=int, default=8, help="Reset sensor after N invalid samples in a row (default: 8)")
    p.add_argument("--reset-i2c", action="store_true", help="Also re-init I2C on reset (slower, but may help)")

    # Verbose
    p.add_argument("--auto-verbose", action="store_true", help="Print auto-range scan details")

    return p.parse_args()


def init_i2c_and_sensor(reset_i2c: bool, i2c_obj):
    """
    Re-initialize sensor; optionally also re-initialize I2C.
    Returns (i2c, sensor).
    """
    if reset_i2c or i2c_obj is None:
        i2c = busio.I2C(board.SCL, board.SDA)
    else:
        i2c = i2c_obj

    sensor = adafruit_tsl2591.TSL2591(i2c)
    return i2c, sensor


def main():
    args = parse_args()

    print("=== TSL2591 Calibration Test ===")
    print("Interface: I2C (SCL/SDA)")
    print("Mode: auto-range always enabled (night-aware)")
    print(f"Samples: {args.samples}, interval: {args.interval}s")
    print(f"Starting SQM constant: {args.sqm_const:.2f}")
    print(f"Calibration CSV: {args.calib_file}")
    print(f"Read retries: {args.read_retries}, min_ch0: {args.min_ch0}, sat_threshold: {args.sat_threshold}")
    print(f"Auto-range target CH0: {args.target_ch0_low}..{args.target_ch0_high}, warmup_reads: {args.warmup_reads}")
    print(f"Policies: rerange_after_invalid={args.rerange_after_invalid}, reset_after_invalid={args.reset_after_invalid}, reset_i2c={args.reset_i2c}")
    print(f"Adafruit API style: {_API_STYLE}")
    print()

    sqm_ref = prompt_sqm_ref()
    if sqm_ref is not None:
        print(f"Calibration enabled: SQM_ref={sqm_ref:.2f}")
    else:
        print("Calibration disabled (no SQM_ref provided).")
    print()

    # init i2c + sensor
    try:
        i2c, sensor = init_i2c_and_sensor(reset_i2c=True, i2c_obj=None)
    except Exception as e:
        print("ERROR: Could not initialize I2C/sensor.")
        print("Hint: run 'i2cdetect -y 1' and look for '29'.")
        print("Exception:", e)
        sys.exit(1)

    # choose settings via night-aware auto-range
    gain_sel, exp_sel = auto_range_night(
        sensor=sensor,
        verbose=args.auto_verbose,
        sat_threshold=args.sat_threshold,
        target_low=args.target_ch0_low,
        target_high=args.target_ch0_high,
        min_ch0_for_valid=args.min_ch0_valid,
        warmup_reads=args.warmup_reads,
    )

    print(f"Auto-range selected: gain={gain_sel}, exposure={exp_sel}ms")
    try:
        set_gain_and_exposure(sensor, gain_sel, exp_sel)
    except Exception as ex:
        print("ERROR: Could not apply auto-range settings:", ex)
        sys.exit(1)

    warmup(sensor, exp_sel, args.warmup_reads)
    settle_for_integration(exp_sel)

    g_now, it_now = get_current_settings(sensor)
    print(f"Active settings: gain={g_now}, integration_time={it_now}")
    print()

    # Calibration stats
    session_consts = []
    invalid_streak = 0

    for idx in range(args.samples):
        timestamp = ts_now()

        # Lux is informational (may be 0 at night)
        try:
            lux = safe_value(sensor.lux)
        except Exception:
            lux = 0.0

        # robust raw read
        try:
            ch0, ch1, note = read_valid_raw(
                sensor=sensor,
                exposure_ms=exp_sel,
                read_retries=args.read_retries,
                retry_delay=args.read_retry_delay,
                min_ch0=args.min_ch0,
                sat_threshold=args.sat_threshold,
            )
        except Exception as e:
            print("ERROR: Failed to read sensor:", e)
            break

        print(f"[{timestamp}] Sample {idx+1}/{args.samples}")

        if ch0 is None:
            invalid_streak += 1
            print("  Raw CH0/CH1 : invalid (0/0, saturated, or too low after retries)")
            print(f"  Lux         : {lux:.3f} lx (info)")
            print(f"  Note        : {note}")
            print()

            # Optional CSV logging: log invalid rows even without SQM_ref (debugging)
            append_csv(args.calib_file, {
                "timestamp": timestamp,
                "gain": gain_sel,
                "exposure_ms": exp_sel,
                "ch0": "",
                "ch1": "",
                "lux": f"{lux:.6f}",
                "sqm_ref": f"{sqm_ref:.3f}" if sqm_ref is not None else "",
                "const_ci": "",
                "valid": "false",
                "note": note,
            })

            # Reset if invalid streak is large
            if args.reset_after_invalid > 0 and invalid_streak >= args.reset_after_invalid:
                print("  Action      : invalid streak -> resetting sensor ...")
                try:
                    i2c, sensor = init_i2c_and_sensor(args.reset_i2c, i2c)
                except Exception as e:
                    print("ERROR: Sensor reset failed:", e)
                    break

                # Re-run auto-range after reset
                gain_sel, exp_sel = auto_range_night(
                    sensor=sensor,
                    verbose=args.auto_verbose,
                    sat_threshold=args.sat_threshold,
                    target_low=args.target_ch0_low,
                    target_high=args.target_ch0_high,
                    min_ch0_for_valid=args.min_ch0_valid,
                    warmup_reads=args.warmup_reads,
                )
                print(f"  New range   : gain={gain_sel}, exposure={exp_sel}ms")
                try:
                    set_gain_and_exposure(sensor, gain_sel, exp_sel)
                except Exception as ex:
                    print("ERROR: Could not apply new settings:", ex)
                    break
                warmup(sensor, exp_sel, args.warmup_reads)
                settle_for_integration(exp_sel)
                invalid_streak = 0
                print()

            # Otherwise rerange sooner
            elif args.rerange_after_invalid > 0 and invalid_streak >= args.rerange_after_invalid:
                print("  Action      : too many invalid reads -> re-running auto-range ...")
                gain_sel, exp_sel = auto_range_night(
                    sensor=sensor,
                    verbose=args.auto_verbose,
                    sat_threshold=args.sat_threshold,
                    target_low=args.target_ch0_low,
                    target_high=args.target_ch0_high,
                    min_ch0_for_valid=args.min_ch0_valid,
                    warmup_reads=args.warmup_reads,
                )
                print(f"  New range   : gain={gain_sel}, exposure={exp_sel}ms")
                try:
                    set_gain_and_exposure(sensor, gain_sel, exp_sel)
                except Exception as ex:
                    print("ERROR: Could not apply new settings:", ex)
                    break
                warmup(sensor, exp_sel, args.warmup_reads)
                settle_for_integration(exp_sel)
                invalid_streak = 0
                print()

            time.sleep(max(0.0, args.interval))
            continue

        # valid sample
        invalid_streak = 0

        sqm_pred = compute_sqm_from_ch0(ch0, args.sqm_const)
        print(f"  Raw CH0/CH1 : {ch0}/{ch1}")
        print(f"  SQM (CH0)   : {sqm_pred:.2f} mag/arcsec^2   (using C={args.sqm_const:.2f})")
        print(f"  Lux         : {lux:.3f} lx (info)")

        const_ci = ""
        valid_flag = "true"

        if sqm_ref is not None:
            ci = compute_const_from_ref(ch0, sqm_ref)
            if math.isfinite(ci):
                session_consts.append(ci)
                const_ci = f"{ci:.6f}"
                print(f"  Calib C_i   : {ci:.4f}")
            else:
                valid_flag = "false"

        append_csv(args.calib_file, {
            "timestamp": timestamp,
            "gain": gain_sel,
            "exposure_ms": exp_sel,
            "ch0": str(ch0),
            "ch1": str(ch1),
            "lux": f"{lux:.6f}",
            "sqm_ref": f"{sqm_ref:.3f}" if sqm_ref is not None else "",
            "const_ci": const_ci,
            "valid": valid_flag if sqm_ref is not None else "true",
            "note": "ok",
        })

        print()
        time.sleep(max(0.0, args.interval))

    # Summary
    if sqm_ref is not None:
        print("=== Calibration Summary ===")

        if len(session_consts) == 0:
            print("Session: no usable calibration samples.")
        else:
            session_med = statistics.median(session_consts)
            session_sd = statistics.pstdev(session_consts) if len(session_consts) >= 2 else float("nan")
            print(f"Session usable samples: {len(session_consts)}")
            print(f"Session recommended sqm_const (median): {session_med:.4f}")
            if math.isfinite(session_sd):
                print(f"Session spread (stdev): {session_sd:.4f}")

        # Re-load all-time after writing
        all_time_consts2 = load_all_time_consts(args.calib_file)
        if len(all_time_consts2) == 0:
            print("All-time: no usable samples in CSV.")
        else:
            all_med = statistics.median(all_time_consts2)
            all_sd = statistics.pstdev(all_time_consts2) if len(all_time_consts2) >= 2 else float("nan")
            print(f"All-time usable samples: {len(all_time_consts2)}")
            print(f"All-time recommended sqm_const (median): {all_med:.4f}")
            if math.isfinite(all_sd):
                print(f"All-time spread (stdev): {all_sd:.4f}")

            print()
            print(f"Test with: python3 tsl2591_kalibration.py --sqm-const {all_med:.4f}")
            print(f"Later config: TSL2591_SQM_CONSTANT = {all_med:.4f}")

    print("\nTSL2591 calibration test finished.")


if __name__ == "__main__":
    main()
