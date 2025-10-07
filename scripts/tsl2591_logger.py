#!/usr/bin/python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from askutils import config
from askutils.utils.logger import log, warn, error
from askutils.utils import influx_writer
from askutils.sensors import tsl2591

def main():
    if not getattr(config, "TSL2591_ENABLED", False):
        print("TSL2591 ist deaktiviert. Test wird übersprungen.")
        return

    if not tsl2591.is_connected():
        error("TSL2591 ist nicht verbunden oder liefert keine Werte.")
        return

    try:
        data = tsl2591.read_tsl2591()
    except Exception as e:
        error(f"❌ Fehler beim Auslesen des TSL2591: {e}")
        return

    print(f"Standort: {config.STANDORT_NAME} ({config.KAMERA_ID})")
    print(f"Lux-Wert      : {data['lux']:.2f} lx")
    print(f"Sichtbar      : {data['visible']}")
    print(f"Infrarot      : {data['infrared']}")
    print(f"Vollspektrum  : {data['full']}")
    print(f"SQM (gesamt)  : {data['sqm']:.2f}")
    print(f"SQM (sichtbar): {data['sqm2']:.2f}")

    influx_writer.log_metric("tsl2591", {
        "Lux": data["lux"],
        "Visible": data["visible"],
        "IR": data["infrared"],
        "Full": data["full"],
        "SQM": data["sqm"],
        "SQM2": data["sqm2"]
    }, tags={"host": "host1"})

if __name__ == "__main__":
    main()
