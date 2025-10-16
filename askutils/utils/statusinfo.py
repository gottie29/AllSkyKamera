# Module fuer den Status der Raspi
import psutil, datetime, subprocess

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