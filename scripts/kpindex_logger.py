#!/usr/bin/python3
import sys
import os
import json
from datetime import datetime, timedelta
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from askutils import config
from askutils.utils.logger import log, warn, error
from askutils.utils import influx_writer


def _fetch_latest_kp(hours_back: int = 10) -> float:
    start = datetime.utcnow() - timedelta(hours=hours_back)
    end = datetime.utcnow()

    time_string = (
        "start=" + start.strftime('%Y-%m-%dT%H:%M:%SZ') +
        "&end=" + end.strftime('%Y-%m-%dT%H:%M:%SZ')
    )
    url = "https://kp.gfz-potsdam.de/app/json/?" + time_string + "&index=Kp"

    r = requests.get(url, timeout=15)
    r.raise_for_status()
    j = r.json()

    kp_list = j.get("Kp")
    if not isinstance(kp_list, list) or not kp_list:
        raise ValueError("Antwort enthält kein gültiges 'Kp' Array")

    kp = kp_list[-1]
    return float(kp)


def _write_overlay(kp_value: float) -> None:
    overlay_dir = os.path.join(config.ALLSKY_PATH, "config", "overlay", "extra")
    os.makedirs(overlay_dir, exist_ok=True)
    overlay_path = os.path.join(overlay_dir, "kpindex_overlay.json")

    overlay_data = {
        "KPINDEX": {
            "value": f"{kp_value:.1f}",
            "format": "{:.1f}"
        }
    }
    with open(overlay_path, "w") as f:
        json.dump(overlay_data, f, indent=2)


def main():
    try:
        # Overlay ist optional; Influx-Logging darf davon NICHT abhängen
        overlay_enabled = bool(getattr(config, "KPINDEX_OVERLAY", False))

        kp = _fetch_latest_kp(hours_back=10)

        # optional: debug file (falls du es wirklich willst)
        try:
            with open("kpindex.json", "w") as f:
                json.dump({"kp_index": kp}, f, indent=2)
        except Exception as e:
            warn(f"Konnte kpindex.json nicht schreiben: {e}")

        print(f"KP Index: {kp:.2f}")

        # Influx immer schreiben
        influx_writer.log_metric(
            "kpindex",
            {"kp_index": float(kp)},
            tags={"host": "host1"}
        )

        # Overlay nur wenn aktiviert
        if overlay_enabled:
            _write_overlay(kp)

    except Exception as e:
        error(f"Fehler beim Auslesen/Schreiben der KPIndex-Daten: {e}")


if __name__ == "__main__":
    main()
