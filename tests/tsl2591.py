#!/usr/bin/env python3
"""
TSL2591 light sensor test script (standalone) with auto-range

- Interface: I2C (busio + Adafruit Blinka)
- Reads lux, visible, IR, full spectrum
- Reads RAW channels CH0/CH1 (raw_luminosity) if available
- Computes SQM-like value (mag/arcsec^2) from CH0:
    SQM = sqm_const - 2.5 * log10(CH0)
  (sqm_const is a calibration constant; default 22.0 for test scaling)

- CLI:
    --gain        low|med|high|max
    --exposure    100|200|300|400|500|600   (ms integration time)
    --samples     number of samples (default 5)
    --interval    seconds between samples (default 2.0)
    --auto-range  enable automatic gain/exposure selection
    --auto-verbose print scan details
    --sqm-const   constant C in SQM = C - 2.5*log10(CH0)

ASCII-only, English-only output.
"""

import argparse
import math
import time
import sys

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


def safe_value(x, fallback=0.0001):
    try:
        if x is None:
            return fallback
        x = float(x)
        if x <= 0:
            return fallback
        return x
    except Exception:
        return fallback


def parse_args():
    p = argparse.ArgumentParser(description="TSL2591 standalone test (gain + exposure + auto-range + SQM-from-RAW).")
    p.add_argument("--gain", default="med", choices=["low", "med", "high", "max"],
                   help="Sensor gain (default: med)")
    p.add_argument("--exposure", type=int, default=200, choices=[100, 200, 300, 400, 500, 600],
                   help="Integration time in ms (default: 200)")
    p.add_argument("--samples", type=int, default=5, help="Number of samples (default: 5)")
    p.add_argument("--interval", type=float, default=2.0, help="Seconds between samples (default: 2.0)")
    p.add_argument("--auto-range", action="store_true",
                   help="Automatically choose gain/exposure to avoid saturation and improve signal.")
    p.add_argument("--auto-verbose", action="store_true",
                   help="Print auto-range scan details.")
    p.add_argument("--sqm-const", type=float, default=22.0,
                   help="SQM constant C for SQM = C - 2.5*log10(CH0). Default: 22.0")
    return p.parse_args()


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


def read_raw_counts(sensor):
    """
    Returns (ch0, ch1) or (None, None) if not available.
    """
    try:
        raw = sensor.raw_luminosity  # expected tuple (ch0, ch1)
        if isinstance(raw, tuple) and len(raw) >= 2:
            ch0 = int(raw[0])
            ch1 = int(raw[1])
            return ch0, ch1
    except Exception:
        pass
    return None, None


def settle_for_integration(exposure_ms: int):
    time.sleep(exposure_ms / 1000.0 + 0.05)


def compute_sqm_from_ch0(ch0: int, sqm_const: float) -> float:
    """
    SQM-like value from CH0 counts.
    """
    if ch0 is None or ch0 <= 0:
        return float("nan")
    return sqm_const - 2.5 * math.log10(float(ch0))


def auto_range(sensor, verbose: bool = False):
    """
    Auto-select gain and exposure by scanning combinations from low sensitivity
    to high sensitivity, aiming for CH0 counts in a target window.
    """
    gain_factors = {"low": 1, "med": 25, "high": 428, "max": 9876}
    gains = ["low", "med", "high", "max"]
    exposures = [100, 200, 300, 400, 500, 600]

    combos = []
    for g in gains:
        for e in exposures:
            combos.append((gain_factors[g] * e, g, e))
    combos.sort(key=lambda x: x[0])  # low -> high sensitivity

    TARGET_LOW = 2000
    TARGET_HIGH = 45000
    SAT_THRESHOLD = 65000  # near 16-bit max

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
            # No raw support; fallback to "lux exists" heuristic (weak but better than nothing)
            try:
                lux = safe_value(sensor.lux, fallback=0.0)
            except Exception:
                lux = 0.0
            score = lux  # prefer non-zero lux
            if verbose:
                print(f"  gain={g:4s} exp={e:3d}ms  (no raw) lux={lux:.3f} score={score:.3f}")
            if best_score is None or score > best_score:
                best_score = score
                best = (g, e)
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

        # Fallback scoring
        if saturated:
            score = -10_000_000 - ch0
        else:
            # prefer higher CH0 without going too high
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


def main():
    args = parse_args()

    print("=== TSL2591 Light Sensor Test ===")
    print("Interface: I2C (SCL/SDA)")
    print(f"Requested: gain={args.gain}, exposure={args.exposure}ms, samples={args.samples}, interval={args.interval}s")
    if args.auto_range:
        print("Mode: auto-range enabled")
    print(f"SQM model: SQM = {args.sqm_const:.2f} - 2.5*log10(CH0)")
    print("This test reads a few samples and then exits.\n")

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
        print("Check wiring and address (default 0x29).")
        print("Hint: run 'i2cdetect -y 1' and look for '29'.")
        print("Exception:", e)
        sys.exit(1)

    # Apply settings
    if args.auto_range:
        g, e = auto_range(sensor, verbose=args.auto_verbose)
        print(f"Auto-range selected: gain={g}, exposure={e}ms\n")
        try:
            set_gain_and_exposure(sensor, g, e)
        except Exception as ex:
            print("ERROR: Auto-range selected settings could not be applied:", ex)
            sys.exit(1)
        settle_for_integration(e)
    else:
        try:
            set_gain_and_exposure(sensor, args.gain, args.exposure)
        except Exception as ex:
            print("ERROR: Could not set gain/exposure:", ex)
            sys.exit(1)
        settle_for_integration(args.exposure)

    g_now, it_now = get_current_settings(sensor)
    print(f"Active settings: gain={g_now}, integration_time={it_now}\n")

    for i in range(args.samples):
        try:
            lux = safe_value(sensor.lux)
            # Keep these for info only (they can be scaled/driver values)
            visible = safe_value(sensor.visible)
            infrared = safe_value(sensor.infrared)
            full = safe_value(sensor.full_spectrum)
            ch0, ch1 = read_raw_counts(sensor)
        except Exception as e:
            print("ERROR: Failed to read data from TSL2591:", e)
            print("Hint: check wiring, power, and run 'i2cdetect -y 1'.")
            break

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        print(f"[{timestamp}] Sample {i+1}/{args.samples}")
        if ch0 is not None:
            sqm = compute_sqm_from_ch0(ch0, args.sqm_const)
            # Saturation check (simple)
            sat = (ch0 >= 65000) or (ch1 >= 65000)
            print(f"  Raw CH0/CH1 : {ch0}/{ch1}" + ("  (SATURATED)" if sat else ""))
            print(f"  SQM (CH0)   : {sqm:.2f} mag/arcsec^2")
        else:
            print("  Raw CH0/CH1 : not available in this library version")

        print(f"  Lux         : {lux:.3f} lx (info)")
        print(f"  Visible     : {visible:.3f} (info)")
        print(f"  Infrared    : {infrared:.3f} (info)")
        print(f"  Full spec   : {full:.3f} (info)")
        print()

        time.sleep(max(0.0, args.interval))

    print("TSL2591 test finished.")


if __name__ == "__main__":
    main()
