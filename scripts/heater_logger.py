#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from askutils.sensors import heater
from askutils.utils.logger import log, warn, error
from askutils.utils import influx_writer


def main():
    try:
        diag = heater.decide()
    except Exception as e:
        error(f"Heater: exception: {e}")
        return

    # Ausgabe
    if not diag.get("enabled", False):
        print("Heater disabled / skipped.")
        return

    print(
        f"Heater: src={diag.get('src')} T_in={diag.get('t_in')} RH={diag.get('rh')} "
        f"DP={diag.get('dewpoint')} spread={diag.get('spread')} T_out={diag.get('t_out')} "
        f"{diag.get('current')} -> {diag.get('desired')} | {diag.get('reason')}"
    )

    # Influx optional (falls du es willst)
    try:
        fields = {
            "relay_on": 1 if diag.get("desired") == "ON" else 0,
            "t_in": diag.get("t_in"),
            "rh": diag.get("rh"),
            "dewpoint": diag.get("dewpoint"),
            "spread": diag.get("spread"),
            "t_out": diag.get("t_out"),
        }
        # None entfernen (Influx mag keine None als Feld)
        fields = {k: v for k, v in fields.items() if v is not None}
        influx_writer.log_metric("heater", fields, tags={"host": "host1"})
    except Exception:
        pass


if __name__ == "__main__":
    main()
