#!/usr/bin/env python3
"""
TSL2591 light sensor test script (standalone)

- Interface: I2C (busio + Adafruit Blinka)
- Reads lux, visible, IR, full spectrum
- Computes sky brightness (mag/arcsec^2)
- Standalone test mode only
- CLI parameters:
    --gain        low|med|high|max
    --exposure    100|200|300|400|500|600   (ms integration time)
    --samples     number of samples (default 5)
    --interval    seconds between samples (default 2.0)
    --auto-range  enable automatic gain/exposure selection

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


def compute_sky_brightness(lux):
    # mag/arcsec^2 = 22 - 2.5 * log10(lux)
    lux = safe_value(lux)
    return 22.0 - 2.5 * math.log10(lux)


def parse_args():
    p = argparse.ArgumentParser(description="TSL2591 standalone test (gain + exposure + auto-range).")
    p.add_argument("--gain", default="med", choices=["low", "med", "high", "max"],
                   help="Sensor gain (default: med)")
    p.add_argument("--exposure", type=int, default=200, choices=[100, 200, 300, 400, 500, 600],
                   help="Integration time in ms (default: 200)")
    p.add_argument("--samples", type=int, default=5, help="Number of samples (default: 5)")
    p.add_argument("--interval", type=float, default=2.0, help="Seconds between samples (default: 2.0)")
    p.add_argument("--auto-range", action="store_true",
                   help="Automatically choose gain/exposure to avoid saturation and improve signal.")
    p.add_argument("--auto-verbose", action="store_true",
                   help="Print auto-range test details.")
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

    # Apply settings (best effort)
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
    Try to read raw channels if library supports it.
    Returns (ch0, ch1) or (None, None).
    """
    try:
        raw = sensor.raw_luminosity  # often tuple (ch0, ch1)
        if isinstance(raw, tuple) and len(raw) >= 2:
            ch0 = int(raw[0])
            ch1 = int(raw[1])
            return ch0, ch1
    except Exception:
        pass
    return None, None


def settle_for_integration(exposure_ms: int):
    # Wait slightly longer than integration time so a fresh sample is ready
    time.sleep(exposure_ms / 1000.0 + 0.05)


def auto_range(sensor, verbose: bool = False):
    """
    Auto-select gain and exposure by scanning combinations from low sensitivity
    to high sensitivity, aiming for raw counts in a target window.
    """
    # Approximate gain factors for sorting by sensitivity
    gain_factors = {"low": 1, "med": 25, "high": 428, "max": 9876}
    gains = ["low", "med", "high", "max"]
    exposures = [100, 200, 300, 400, 500, 600]

    # Sensitivity score (for ordering)
    combos = []
    for g in gains:
        for e in exposures:
            combos.append((gain_factors[g] * e, g, e))
    combos.sort(key=lambda x: x[0])  # low -> high sensitivity

    # Target window for CH0 counts (heuristic)
    # We want: not saturated, but not too low.
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

        # If raw not available, fall back to a weaker heuristic using full_spectrum
        if ch0 is None:
            try:
                full = safe_value(sensor.full_spectrum)
                lux = sensor.lux
                # Heuristic: prefer nonzero lux and a moderate full-spectrum number
                # (full is not counts; still helps to avoid extreme settings)
                if lux is None or lux <= 0:
                    metric = 0.0
                else:
                    metric = full
            except Exception:
                metric = 0.0

            # Score: prefer metric in a mid range, avoid zeros
            if metric <= 0:
                score = -1
            else:
                # "closer to 10000 is better" arbitrary
                score = -abs(metric - 10000.0)

            if verbose:
                print(f"  gain={g:4s} exp={e:3d}ms  metric={metric:.1f}  score={score:.1f}")

            if best_score is None or score > best_score:
                best_score = score
                best = (g, e)

            continue

        # Raw-based evaluation
        saturated = (ch0 >= SAT_THRESHOLD) or (ch1 >= SAT_THRESHOLD)
        too_dark = (ch0 < TARGET_LOW)
        in_window = (TARGET_LOW <= ch0 <= TARGET_HIGH) and not saturated

        if verbose:
            print(f"  gain={g:4s} exp={e:3d}ms  CH0={ch0:5d} CH1={ch1:5d}  "
                  f"{'SAT' if saturated else ''}{'DARK' if too_dark else ''}{'OK' if in_window else ''}")

        if in_window:
            # First OK in ascending sensitivity is usually best
            return g, e

        # Track best fallback:
        # - if everything is too dark -> choose highest sensitivity (max ch0 without saturation)
        # - if everything saturates -> choose lowest sensitivity that is not saturated (or minimal)
        if saturated:
            # Penalize saturation strongly
            score = -10_000_000 - ch0
        else:
            # Prefer larger counts (more SNR) up to TARGET_HIGH
            # If too dark, higher is better; if too bright but not saturated, closer to TARGET_HIGH is better
            if ch0 <= TARGET_HIGH:
                score = ch0
            else:
                score = TARGET_HIGH - (ch0 - TARGET_HIGH)  # degrade if beyond target

        if best_score is None or score > best_score:
            best_score = score
            best = (g, e)

    # If nothing hit window, return best fallback
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
    else:
        try:
            set_gain_and_exposure(sensor, args.gain, args.exposure)
        except Exception as ex:
            print("ERROR: Could not set gain/exposure:", ex)
            sys.exit(1)

    g_now, it_now = get_current_settings(sensor)
    print(f"Active settings: gain={g_now}, integration_time={it_now}\n")

    for i in range(args.samples):
        try:
            lux = safe_value(sensor.lux)
            visible = safe_value(sensor.visible)
            infrared = safe_value(sensor.infrared)
            full = safe_value(sensor.full_spectrum)
            ch0, ch1 = read_raw_counts(sensor)
        except Exception as e:
            print("ERROR: Failed to read data from TSL2591:", e)
            print("Hint: check wiring, power, and run 'i2cdetect -y 1'.")
            break

        skybright = compute_sky_brightness(lux)
        skybright2 = compute_sky_brightness(visible)

        # Keep your original behavior
        if skybright2 < 6.0:
            skybright2 = 0.0001

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        print(f"[{timestamp}] Sample {i+1}/{args.samples}")
        print(f"  Lux        : {lux:.3f} lx")
        print(f"  Visible    : {visible:.3f}")
        print(f"  Infrared   : {infrared:.3f}")
        print(f"  Full spec  : {full:.3f}")
        if ch0 is not None:
            print(f"  Raw CH0/CH1 : {ch0}/{ch1}")
        print(f"  SkyBright  : {skybright:.2f} mag/arcsec^2")
        print(f"  SkyBrightVis: {skybright2:.2f} mag/arcsec^2")
        print()

        time.sleep(max(0.0, args.interval))

    print("TSL2591 test finished.")


if __name__ == "__main__":
    main()
