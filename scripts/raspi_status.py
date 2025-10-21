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
cpu_pct  = statusinfo.get_cpu_usage()
mem      = statusinfo.get_memory_usage()

# Debug-Ausgabe
print("\n=== Raspberry Pi Status ===")
print(f"Temperatur : {temp:6.2f} Grad Celcius")
print(f"CPU        : {cpu_pct:6.1f} Prozent")
print(f"RAM        : {mem['percent']:6.1f} Prozent ({mem['used_mb']:.0f}/{mem['total_mb']:.0f} MB)")
print(f"Speicher   : {disk['percent']:6.1f} Prozent ({disk['free_mb']:.0f} MB frei)")
print(f"Laufzeit   : {uptime:>6d} s")
print(f"Spannung   : {voltage:6.2f} V")
print("==============================\n")


# Daten an Influx senden
influx_writer.log_metric("raspistatus", {
    "raspiTemp": float(temp),
    "raspiDiskUsage": float(disk["used_mb"]),
    "raspiDiskFree": float(disk["free_mb"]),
    "raspiBootime": float(uptime),
    "voltage": float(voltage),
    "raspiCpuPercent":  float(cpu_pct),
    "raspiMemPercent":  float(mem["percent"]),
    "raspiMemUsedMB":   float(mem["used_mb"]),
    "raspiMemTotalMB":  float(mem["total_mb"]),
    "online": 1.0
}, tags={"host": "host1"})
