import psutil
import json
import os

# State-Datei direkt neben diesem Modul
STATE_FILE = os.path.join(os.path.dirname(__file__), "netstatus_state.json")
# Interfaces, die wir überwachen wollen
INTERFACES = ["eth0", "wlan0"]

def _read_last_state():
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
        return data.get("bytes_sent", 0), data.get("bytes_recv", 0)
    except Exception:
        # z.B. Datei nicht vorhanden → Erster Lauf
        return None, None

def _write_state(sent, recv):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"bytes_sent": sent, "bytes_recv": recv}, f)
    os.replace(tmp, STATE_FILE)

def get_net_io():
    """Liefert kumulierte Bytes (sent, recv) über eth0 + wlan0 seit Boot."""
    counters = psutil.net_io_counters(pernic=True)
    total_sent = 0
    total_recv = 0
    for iface in INTERFACES:
        if iface in counters:
            total_sent += counters[iface].bytes_sent
            total_recv += counters[iface].bytes_recv
    return total_sent, total_recv

def get_net_usage_mb():
    """
    Liest den letzten Lauf aus STATE_FILE, berechnet die Differenz
    und schreibt den aktuellen Stand zurück.
    Rückgabe: (sent_mb, recv_mb) seit letztem Aufruf.
    Beim ersten Lauf (keine STATE_FILE) wird (0.0, 0.0) zurückgegeben.
    """
    last_sent, last_recv = _read_last_state()
    curr_sent, curr_recv = get_net_io()

    if last_sent is None:
        # Erster Aufruf: keine Differenz
        delta_sent = 0
        delta_recv = 0
    else:
        delta_sent = curr_sent - last_sent
        delta_recv = curr_recv - last_recv

    # State aktualisieren
    _write_state(curr_sent, curr_recv)

    # Bytes → MB
    sent_mb = delta_sent / (1024**2)
    recv_mb = delta_recv / (1024**2)
    return sent_mb, recv_mb
