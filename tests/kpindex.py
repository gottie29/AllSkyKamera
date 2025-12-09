#!/usr/bin/env python3
"""
KP Index Fetch Script

- Queries the GFZ Potsdam API for the last available Kp value
- Handles missing data and errors gracefully
- ASCII-only, English-only
"""

from datetime import datetime, timedelta
import json
import requests
import sys


def fetch_kp_index():
    start = datetime.utcnow() - timedelta(hours=10)
    end   = datetime.utcnow()

    time_string = (
        "start=" + start.strftime("%Y-%m-%dT%H:%M:%SZ")
        + "&end=" + end.strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    url = "https://kp.gfz-potsdam.de/app/json/?" + time_string + "&index=Kp"

    print("Requesting:", url)

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print("ERROR: Failed to request KP index:", e)
        sys.exit(1)

    try:
        data = response.json()
    except Exception as e:
        print("ERROR: Could not decode JSON:", e)
        sys.exit(1)

    # Validate JSON structure
    if "Kp" not in data or not isinstance(data["Kp"], list):
        print("ERROR: API response does not contain expected 'Kp' field")
        sys.exit(1)

    if not data["Kp"]:
        print("ERROR: KP list is empty, no data available")
        sys.exit(1)

    kp_latest = data["Kp"][-1]
    result = {"kp_index": kp_latest}

    print("Latest KP index:", kp_latest)

    # Write to file
    #try:
    #    with open("kpindex.json", "w") as f:
    #        json.dump(result, f)
    #    print("Saved kpindex.json")
    #except Exception as e:
    #    print("ERROR: Could not write kpindex.json:", e)

    return kp_latest


if __name__ == "__main__":
    fetch_kp_index()
