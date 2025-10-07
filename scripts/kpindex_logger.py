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

def main():
    try:
        if config.KPINDEX_OVERLAY:
            
            start       = datetime.now() - timedelta(hours = 10)
            end         = datetime.now()
            time_string = "start=" + start.strftime('%Y-%m-%dT%H:%M:%SZ') + "&end=" + end.strftime('%Y-%m-%dT%H:%M:%SZ')
            url         = 'https://kp.gfz-potsdam.de/app/json/?' + time_string + "&index=Kp"
            response    = requests.get(url)
            response.raise_for_status()
            data        = response.json()
            data        = {"kp_index": data["Kp"][-1]}

            with open("kpindex.json", 'w') as f:
                print("KP Index: " + str(data))
                #json.dump(data, f)

            influx_writer.log_metric("kpindex", {
                "kp_index": float(data['kp_index']),
            }, tags={"host": "host1"})

            overlay_dir = os.path.join(config.ALLSKY_PATH, "config", "overlay", "extra")
            os.makedirs(overlay_dir, exist_ok=True)
            overlay_path = os.path.join(overlay_dir, "kpindex_overlay.json")
            overlay_data = {
                "KPINDEX": {
                    "value": f"{data['kp_index']:.1f}",
                    "format": "{:.1f}"
                },
            }
            with open(overlay_path, "w") as f:
                json.dump(overlay_data, f, indent=2)
            
    except Exception as e:
        error(f"Fehler beim Auslesen oder Schreiben der KPIndex-Daten: {e}")

if __name__ == "__main__":
    main()

