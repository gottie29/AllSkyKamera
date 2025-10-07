############################################
# Abfrage des Raspi-Statuses
# Aufruf im Hauptverzeichnis AllskyKamera mit:
# python3 -m scripts.raspi_status
############################################

from askutils.utils import statusinfo
from askutils.utils.logger import log, warn, error
from askutils.utils import influx_writer
from askutils import config

# Sicherheit: API-Key muss gesetzt sein
if not config.API_KEY or config.API_KEY.strip() == "":
    error("Kein API-Key gesetzt - Skript wird abgebrochen.")
    exit(1)

# Systemwerte abrufen
temp = statusinfo.get_temp()
disk = statusinfo.get_disk_usage()
voltage = statusinfo.get_voltage()
uptime = statusinfo.get_boot_time_seconds()

# Debug-Ausgabe
print(f"Temp: {temp:.2f} °C, Disk: {disk['used_mb']:.1f} MB used, Voltage: {voltage:.2f} V")

# Daten an Influx senden
influx_writer.log_metric("raspistatus", {
    "raspiTemp": float(temp),
    "raspiDiskUsage": float(disk["used_mb"]),
    "raspiDiskFree": float(disk["free_mb"]),
    "raspiBootime": float(uptime),
    "voltage": float(voltage),
    "online": 1.0
}, tags={"host": "host1"})
