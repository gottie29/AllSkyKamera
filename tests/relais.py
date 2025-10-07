#!/usr/bin/env python3
# Datei: relay.py
import argparse
import os
import sys
import RPi.GPIO as GPIO

# === Einstellungen ===
RELAIS_PIN = 26                 # Dein IN liegt auf GPIO26 (BCM)
STATE_DIR = "."                 # Verzeichnis für Zustandsdatei
STATE_FILE = os.path.join(STATE_DIR, f"relay_{RELAIS_PIN}.state")  # Inhalt: "ON" oder "OFF"

# === Helper ===
def ensure_state_dir():
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
    except PermissionError:
        print(f"Keine Schreibrechte für {STATE_DIR}. Starte mit sudo oder passe STATE_DIR an.", file=sys.stderr)
        sys.exit(1)

def read_state():
    if not os.path.isfile(STATE_FILE):
        return "OFF"
    try:
        with open(STATE_FILE, "r") as f:
            val = f.read().strip().upper()
            return "ON" if val == "ON" else "OFF"
    except Exception:
        return "OFF"

def write_state(state):
    with open(STATE_FILE, "w") as f:
        f.write("ON" if state == "ON" else "OFF")

def gpio_level_for(state):
    # High-aktiv bzw. NC/NO vertauscht: ON -> HIGH (zieht an), OFF -> LOW (fällt ab)
    return GPIO.HIGH if state == "ON" else GPIO.LOW

def apply_state(state):
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RELAIS_PIN, GPIO.OUT, initial=gpio_level_for(state))
    # KEIN GPIO.cleanup(): Pin-Pegel bleibt nach Skriptende erhalten

def main():
    parser = argparse.ArgumentParser(
        description="Relais an GPIO26 schalten (ON/OFF/TOGGLE/STATUS) und Zustand persistent halten."
    )
    parser.add_argument("cmd", choices=["on", "off", "toggle", "status", "restore"],
                        help="Aktion: on/off/toggle/status/restore")
    args = parser.parse_args()

    ensure_state_dir()
    last = read_state()

    if args.cmd == "status":
        print(last)
        apply_state(last)
        print(f"Pin gesetzt für Zustand: {last}")
        return

    if args.cmd == "restore":
        apply_state(last)
        print(f"Zustand wiederhergestellt: {last}")
        return

    if args.cmd == "on":
        new = "ON"
    elif args.cmd == "off":
        new = "OFF"
    else:  # toggle
        new = "OFF" if last == "ON" else "ON"

    apply_state(new)
    write_state(new)
    print(f"Relais: {last} -> {new}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

