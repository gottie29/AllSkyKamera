# askutils/utils/influx_writer.py

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from askutils import config
from askutils.utils.logger import log, error

def _get_client():
    if not config.INFLUX_URL or not config.INFLUX_TOKEN:
        error("Influx-Konfiguration fehlt.")
        return None
    return InfluxDBClient(
        url=config.INFLUX_URL,
        token=config.INFLUX_TOKEN,
        org=config.INFLUX_ORG
    )

def log_metric(measurement, fields: dict, tags: dict = None):
    """
    Speichert einen oder mehrere Werte in InfluxDB.
    :param measurement: z.B. "raspistatus"
    :param fields: Messwerte als dict, z.B. {"temp": 42.0}
    :param tags: optionale weitere Tags, z.B. {"host": "host1"}
    """
    client = _get_client()
    if not client:
        return

    write_api = client.write_api(write_options=SYNCHRONOUS)

    point = Point(measurement).tag("kamera", config.KAMERA_ID)

    if tags:
        for k, v in tags.items():
            point = point.tag(k, v)

    for key, val in fields.items():
        point = point.field(key, val)

    try:
        write_api.write(bucket=config.INFLUX_BUCKET, record=point)
        log(f"{measurement}: {fields} -> Influx geschrieben")
    except Exception as e:
        error(f"Influx Write fehlgeschlagen: {e}")
    finally:
        client.close()
