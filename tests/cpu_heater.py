#!/usr/bin/env python3
"""
CPU Heater Test Script
- Generates controlled CPU load (25/50/75/100 percent)
- Stops automatically after a given duration
- Stops early if CPU temperature exceeds a safety limit
- Prints periodic status updates
"""

import time
import os
import argparse

# Try to import psutil (required)
try:
    import psutil
except ImportError:
    print("[ERROR] Python module 'psutil' is not installed.")
    print("        Install with:")
    print("        sudo apt-get update")
    print("        sudo apt-get install python3-psutil")
    raise SystemExit(1)

from multiprocessing import Process

DEFAULT_DURATION = 600         # fallback runtime in seconds
STATUS_INTERVAL = 10           # status update interval
MAX_TEMP_C = 60.0              # safety shutdown limit
PERIOD_SEC = 0.1               # duty-cycle timing window


def get_cpu_temp():
    """Read Raspberry Pi CPU temperature from sysfs."""
    path = "/sys/class/thermal/thermal_zone0/temp"
    try:
        with open(path, "r") as f:
            return float(f.read().strip()) / 1000.0
    except FileNotFoundError:
        print("[WARNING] CPU temperature file not found:")
        print("          /sys/class/thermal/thermal_zone0/temp")
        print("          Temperature monitoring disabled.")
        return None
    except Exception as e:
        print(f"[WARNING] Could not read CPU temperature: {e}")
        return None


def burn(load_pct):
    """
    Create CPU load on one core using duty-cycle logic.
    Runs forever until terminated.
    """
    load = max(0, min(load_pct, 100)) / 100.0

    if load <= 0:
        # Idle loop
        while True:
            time.sleep(1.0)

    busy_time = PERIOD_SEC * load
    idle_time = PERIOD_SEC - busy_time

    while True:
        start = time.perf_counter()
        # Busy loop
        while (time.perf_counter() - start) < busy_time:
            pass
        # Idle time
        if idle_time > 0:
            time.sleep(idle_time)


def main():
    parser = argparse.ArgumentParser(
        description="CPU Heater with selectable load percentage and optional duration."
    )
    parser.add_argument(
        "load",
        type=int,
        choices=[25, 50, 75, 100],
        help="Target CPU load percentage."
    )
    parser.add_argument(
        "duration",
        type=int,
        nargs="?",
        default=DEFAULT_DURATION,
        help=f"Runtime in seconds (default: {DEFAULT_DURATION})."
    )
    args = parser.parse_args()

    load_pct = args.load
    duration = max(1, args.duration)

    cpu_count = os.cpu_count() or 1

    print("=== CPU Heater Test ===")
    print(f"Detected CPU cores : {cpu_count}")
    print(f"Requested CPU load : {load_pct} percent per core")
    print(f"Runtime limit      : {duration} seconds")
    print(f"Temperature limit  : {MAX_TEMP_C:.1f} C")
    print("Temperature source : /sys/class/thermal/thermal_zone0/temp")
    print("psutil version     :", psutil.__version__)
    print()

    # Start worker processes
    processes = []
    for _ in range(cpu_count):
        p = Process(target=burn, args=(load_pct,))
        p.daemon = True
        p.start()
        processes.append(p)

    start_time = time.time()
    next_status = 0
    last_temp = None

    while True:
        elapsed = time.time() - start_time
        remaining = int(duration - elapsed)

        # Check temperature
        current_temp = get_cpu_temp()
        if current_temp is not None:
            last_temp = current_temp
            if current_temp >= MAX_TEMP_C:
                print(f"[INFO] Temperature limit reached: {current_temp:.1f} C >= {MAX_TEMP_C:.1f} C")
                break

        if remaining <= 0:
            print("[INFO] Runtime limit reached. Stopping heater.")
            break

        # Periodic status output
        if elapsed >= next_status:
            cpu_load = psutil.cpu_percent(interval=0.1)
            temp_text = f"{last_temp:.1f} C" if last_temp is not None else "n/a"
            print(f"Remaining: {remaining:4d} s | CPU load: {cpu_load:5.1f}% | Temp: {temp_text}")
            next_status += STATUS_INTERVAL

        time.sleep(0.2)

    # Stop worker processes
    for p in processes:
        p.terminate()

    print("[INFO] All heater processes terminated.")
    print("=== Test Complete ===")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user. Exiting.")
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        raise
