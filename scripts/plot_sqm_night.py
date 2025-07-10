# File: scripts/plot_sqm_night.py
#!/usr/bin/env python3

"""
Erstellt um 08:00 Uhr ein Plot der SQM-Werte der letzten Nacht (12:00–12:00).
"""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from influxdb_client import InfluxDBClient

from askutils import config
from askutils.utils.logger import log, error

def main():
    tz = ZoneInfo(config.TIMEZONE)
    now = datetime.now(tz)
    date0 = (now - timedelta(days=1)).date()  # letzte Nacht
    start = datetime.combine(date0, datetime.min.time(), tz) + timedelta(hours=12)
    end   = start + timedelta(days=1)

    # InfluxDB-Abfrage
    client = InfluxDBClient(url=config.INFLUX_URL,
                            token=config.INFLUX_TOKEN,
                            org=config.INFLUX_ORG)
    query_api = client.query_api()
    query = (
        f'from(bucket:"{config.INFLUX_BUCKET}") '
        f'|> range(start: {start.isoformat()}, stop: {end.isoformat()}) '
        '|> filter(fn: (r) => r._measurement == "sqm" and r._field == "mu")'
    )
    try:
        tables = query_api.query(query)
        times, values = [], []
        for table in tables:
            for record in table.records:
                times.append(record.get_time())
                values.append(record.get_value())
    except Exception as e:
        error(f"Influx-Abfrage fehlgeschlagen: {e}")
        return

    # Plot
    plt.figure(figsize=(12, 6))
    plt.plot(times, values, marker='o', linestyle='-',
             label='Himmelshelligkeit (mag/arcsec²)')
    plt.title(f'SQM-Nachtplot {date0.isoformat()}', fontsize='small')
    plt.xlabel('Zeit', fontsize='small')
    plt.ylabel('mag/arcsec²', fontsize='small')
    plt.grid(True)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=tz))
    plt.gcf().autofmt_xdate()

    # Speichern
    out_dir = os.path.join(config.ALLSKY_PATH, 'plots')
    os.makedirs(out_dir, exist_ok=True)
    fname = os.path.join(out_dir, f'sqm_nacht_{date0.strftime("%Y%m%d")}.png')
    plt.savefig(fname, dpi=150)
    log(f"SQM-Plot gespeichert: {fname}")

if __name__ == '__main__':
    main()
