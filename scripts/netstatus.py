#!/usr/bin/env python3
############################################
# Abfrage des Netzwerk-Traffics
# Aufruf im Hauptverzeichnis AllSkyKamera mit:
# python3 -m scripts.netstatus
############################################

import os
from askutils.utils.netstatus import get_net_usage_mb
from askutils.utils.logger import log, warn, error
from askutils.utils import influx_writer
from askutils import config

# Sicherheit: API-Key muss gesetzt sein
if not config.API_KEY or config.API_KEY.strip() == "":
    error("Kein API-Key gesetzt - Skript wird abgebrochen.")
    exit(1)

# Traffic seit letztem Lauf ermitteln (in MB)
sent_mb, recv_mb = get_net_usage_mb()

# Debug-Ausgabe
log(f"Net Sent: {sent_mb:.2f} MB, Recv: {recv_mb:.2f} MB")

# Daten an Influx senden
influx_writer.log_metric(
    "netstatus",
    {
        "net_sent_mb": float(sent_mb),
        "net_recv_mb": float(recv_mb),
    },
    tags={"host": config.HOSTNAME if hasattr(config, "HOSTNAME") else os.uname().nodename}
)
