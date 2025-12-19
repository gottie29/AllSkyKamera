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
        print("TSL2591 ist deaktiviert. Test wird uebersprungen.")
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
    print(f"Lux-Wert         : {data['lux']:.4f} lx")
    print(f"Sichtbar         : {data['visible']}")
    print(f"Infrarot         : {data['infrared']}")
    print(f"Vollspektrum     : {data['full']}")
    print(f"RAW CH0/CH1      : {data['ch0']}/{data['ch1']}  (note: {data['read_note']})")
    print(f"IR-Ratio CH1/CH0 : {data['ir_ratio']}")
    print(f"SQM (RAW CH0)    : {data['sqm_raw']:.3f}   (C={data['sqm_const']:.2f})")
    print(f"SQM (lux legacy) : {data['sqm']:.3f}")
    print(f"SQM (vis legacy) : {data['sqm2']:.3f}")
    print(f"CloudScore       : {data.get('cloud_score', -1.0)} (0..1)")
    print(f"CloudIndex       : {data.get('cloud_index', -1)} (0=clear .. 3=overcast)")
    print(f"Gain             : {data['gain']}")
    print(f"Integration      : {data['integration_ms']} ms (Auto-Range: {data['autorange']} / {data['autorange_reason']})")

    # Numeric gain code for easier plotting
    gain_numeric_map = {"LOW": 1, "MED": 25, "HIGH": 428, "MAX": 9876}
    gain_code = gain_numeric_map.get(data["gain"], 0)

    # Quality flag
    good_read = 1 if data.get("read_note") == "ok" and data.get("ch0", 0) > 0 else 0

    # IMPORTANT: your camera tag is named 'kamera'
    tags = {
        "host": "host1",
        "kamera": getattr(config, "KAMERA_ID", "UNKNOWN"),
    }

    fields = {
        # Informational values (can be small / not reliable at night)
        "Lux": float(data["lux"]),
        "Visible": int(data["visible"]),
        "IR": int(data["infrared"]),
        "Full": int(data["full"]),

        # RAW channels
        "CH0": int(data["ch0"]),
        "CH1": int(data["ch1"]),
        "IRRatio": float(data["ir_ratio"]),

        # SQM values
        "SQM_RAW": float(data["sqm_raw"]),   # preferred
        "SQM_LUX": float(data["sqm"]),       # legacy
        "SQM_VIS": float(data["sqm2"]),      # legacy
        "SQM_CONST": float(data["sqm_const"]),

        # Cloud metrics
        "CloudScore": float(data.get("cloud_score", -1.0)),
        "CloudIndex": int(data.get("cloud_index", -1)),

        # Settings/state
        "IntegrationMs": int(data["integration_ms"]),
        "GainCode": int(gain_code),
        "AutoRange": 1 if data["autorange"] else 0,
        "GoodRead": int(good_read),
    }

    influx_writer.log_metric("tsl2591", fields, tags=tags)


if __name__ == "__main__":
    main()
