# Module fuer den Status der Raspi
import os
import psutil
import datetime
import subprocess
from askutils import config

def get_temp():
    sensors = psutil.sensors_temperatures()
    if "cpu_thermal" in sensors and sensors["cpu_thermal"]:
        return sensors["cpu_thermal"][0].current
    return 0.0

def get_disk_usage():
    disk = psutil.disk_usage('/')
    return {
        "used_mb": disk.used / 1048576,
        "free_mb": disk.free / 1048576,
        "percent": disk.percent
    }

def get_boot_time_seconds():
    return int(datetime.datetime.now().timestamp() - psutil.boot_time())

def get_voltage():
    try:
        result = subprocess.run(["vcgencmd", "measure_volts"], capture_output=True, text=True)
        return float(result.stdout.strip().replace("volt=", "").replace("V", ""))
    except Exception:
        return 0.0

def get_cpu_usage():
    """Aktuelle CPU-Auslastung in Prozent"""
    return psutil.cpu_percent(interval=1)

def get_memory_usage():
    """Aktueller Arbeitsspeicher-Verbrauch"""
    mem = psutil.virtual_memory()
    return {
        "used_mb": mem.used / 1048576,
        "total_mb": mem.total / 1048576,
        "percent": mem.percent
    }
    
def get_camera_sensor_temperature():
    """
    Lies die SensorTemperature aus metadata.txt im tmp-Verzeichnis
    unterhalb von config.ALLSKY_PATH.

    Erwartetes Format der Datei (Ausschnitt):
        ...
        SensorTemperature=19.000000

    Rueckgabewert:
        float: Temperatur in °C, falls vorhanden
        None : falls Datei nicht existiert oder kein Wert gelesen werden kann
    """
    meta_path = os.path.join(config.ALLSKY_PATH, "tmp", "metadata.txt")

    if not os.path.isfile(meta_path):
        return None

    try:
        with open(meta_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("SensorTemperature="):
                    value_str = line.split("=", 1)[1].strip()
                    # "19.000000" -> 19.0
                    return float(value_str)
    except Exception:
        # Bei allen Fehlern einfach None zurueckgeben,
        # damit der Aufrufer damit umgehen kann.
        return None

    return None