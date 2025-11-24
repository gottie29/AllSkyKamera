#!/usr/bin/env python3
import time
import os
import psutil
import argparse
from multiprocessing import Process

DEFAULT_DURATION = 600            # Standardlaufzeit, falls nichts angegeben wird
STATUS_INTERVAL  = 10             # Status alle 10 Sekunden
MAX_TEMP_C       = 60.0           # Abschaltgrenze in °C
PERIOD_SEC       = 0.1            # Zeitfenster für Duty-Cycle


def get_temp():
    """Temperatur des Raspberry Pi auslesen (CPU-Temp)."""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return float(f.read().strip()) / 1000.0
    except Exception:
        return None


def burn(load_pct):
    """
    CPU-Burner mit Duty-Cycle, um ungefähr load_pct % CPU-Last zu erzeugen.
    Läuft in einem eigenen Prozess (für einen Kern).
    """
    load = max(0, min(load_pct, 100)) / 100.0

    if load <= 0:
        while True:
            time.sleep(1.0)

    busy_time = PERIOD_SEC * load
    idle_time = PERIOD_SEC - busy_time

    while True:
        start = time.perf_counter()
        while (time.perf_counter() - start) < busy_time:
            pass
        if idle_time > 0:
            time.sleep(idle_time)


def main():
    # Argumente
    parser = argparse.ArgumentParser(
        description="CPU-Heizer mit wählbarer Last (25/50/75/100 %) und optionaler Dauer."
    )
    parser.add_argument(
        "load",
        type=int,
        choices=[25, 50, 75, 100],
        help="Ziel-CPU-Last in Prozent (25, 50, 75 oder 100)."
    )
    parser.add_argument(
        "duration",
        type=int,
        nargs="?",
        default=DEFAULT_DURATION,
        help=f"Laufzeit in Sekunden (Standard: {DEFAULT_DURATION})."
    )
    args = parser.parse_args()

    load_pct = args.load
    duration = max(1, args.duration)

    cpu_count = os.cpu_count() or 1
    print(f"Starte CPU-Heizer mit {cpu_count} Prozessen.")
    print(f"Ziel-CPU-Last: {load_pct}% pro Kern.")
    print(f"Laufzeit: {duration} Sekunden.")
    print(f"Temperaturabschaltung bei {MAX_TEMP_C:.1f} °C.\n")

    # Prozesse starten
    procs = []
    for _ in range(cpu_count):
        p = Process(target=burn, args=(load_pct,))
        p.daemon = True
        p.start()
        procs.append(p)

    start = time.time()
    next_status = 0
    last_temp = None

    while True:
        elapsed = time.time() - start
        remaining = int(duration - elapsed)

        # Temperatur prüfen
        current_temp = get_temp()
        if current_temp is not None:
            last_temp = current_temp
            if current_temp >= MAX_TEMP_C:
                print(f"Maximaltemperatur erreicht: {current_temp:.1f} °C (Grenze {MAX_TEMP_C:.1f} °C).")
                break

        # Zeitlimit erreicht?
        if remaining <= 0:
            print("Zeitlimit erreicht. Heizer beendet.")
            break

        # Status-Ausgabe
        if elapsed >= next_status:
            cpu = psutil.cpu_percent(interval=0.1)
            temp_display = f"{last_temp:.1f} °C" if last_temp is not None else "n/a"
            print(f"Restzeit: {remaining:4d} s | CPU-Last: {cpu:5.1f}% | Temperatur: {temp_display}")
            next_status += STATUS_INTERVAL

        time.sleep(0.2)

    # Prozesse stoppen
    for p in procs:
        p.terminate()

    print("Alle Heizer-Prozesse beendet.")


if __name__ == "__main__":
    main()
