#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AllSkyKamera Control-Poller (cronfreundlich, Einzeldurchlauf)

- arbeitet direkt in config.FTP_REMOTE_DIR (wie askutils/uploader/config_upload)
- Locking per RNFR/RNTO: control.json -> control.processing.json
- Delete-on-success, Fehlerpfad mit control.error.json
- Beendet sich sofort, wenn keine control.json vorhanden ist
- Unterstuetzte Commands:
    - upload_last_batch  → ruft dein run_nightly_upload.py auf
    - upload_config      → ruft askutils.uploader.config_upload auf
    - lib_start / lib_stop → ruft ~/AllSkyKamera/startstop.sh auf
    - reboot             → fuehrt System-Reboot am Ende aus
"""

import ftplib
import io
import json
import os
import subprocess
import time
import socket
import posixpath

from askutils import config

# ===== Konfiguration =====
FTP_HOST = getattr(config, "FTP_SERVER", None)
FTP_USER = getattr(config, "FTP_USER", None)
FTP_PASS = getattr(config, "FTP_PASS", None)
REMOTE_DIR = getattr(config, "FTP_REMOTE_DIR", None)
CAM_ID = getattr(config, "KAMERA_ID", "ASK???")

SRC_NAME  = "control.json"
PROC_NAME = "control.processing.json"
ERR_NAME  = "control.error.json"

FTP_TIMEOUT = 20

# ==== FTP-Helfer ====

def rpath(name):
    """Erzeuge einen absoluten Remote-Pfad innerhalb REMOTE_DIR."""
    if not REMOTE_DIR:
        return "/" + name.lstrip("/")
    base = REMOTE_DIR if REMOTE_DIR.startswith("/") else "/" + REMOTE_DIR
    return posixpath.join(base, name)

def ftp_connect():
    """FTP-Verbindung aufbauen."""
    if not FTP_HOST or not FTP_USER or not FTP_PASS:
        raise RuntimeError("FTP-Config unvollstaendig (FTP_SERVER/USER/PASS).")
    if not REMOTE_DIR:
        raise RuntimeError("FTP_REMOTE_DIR ist nicht gesetzt.")
    ftp = ftplib.FTP(FTP_HOST, timeout=FTP_TIMEOUT)
    ftp.login(FTP_USER, FTP_PASS)
    return ftp

def ftp_try_lock(ftp):
    """control.json -> control.processing.json; True, wenn Lock erfolgreich."""
    try:
        ftp.rename(rpath(SRC_NAME), rpath(PROC_NAME))
        return True
    except ftplib.error_perm:
        return False

def ftp_download(ftp, name):
    """Lade Datei (by name relativ zu REMOTE_DIR) -> bytes."""
    buf = io.BytesIO()
    ftp.retrbinary(f"RETR {rpath(name)}", buf.write)
    return buf.getvalue()

def ftp_upload_bytes(ftp, name, data_bytes):
    """Lade Bytes nach REMOTE_DIR/name hoch."""
    ftp.storbinary(f"STOR {rpath(name)}", io.BytesIO(data_bytes))

def ftp_delete_safe(ftp, name):
    try:
        ftp.delete(rpath(name))
    except ftplib.error_perm:
        pass


# ==== Command-Helfer ====

def run_cmd(cmd):
    """Starte externen Prozess; Rueckgabe: Return-Code."""
    try:
        return subprocess.call(cmd)
    except Exception:
        return 1

def cmd_upload_last_batch():
    """Ruft dein nightly-upload Skript auf."""
    script_path = os.path.expanduser("~/AllSkyKamera/scripts/run_nightly_upload.py")
    return run_cmd(["/usr/bin/python3", script_path])

def cmd_upload_config():
    """Erstellt & laedt config.json per FTP hoch (dein gezeigter Flow)."""
    try:
        from askutils.uploader import config_upload
    except Exception:
        return 1
    try:
        json_path = config_upload.create_config_json("config.json")
        if not json_path:
            return 1
        config_upload.upload_to_ftp(json_path)
        return 0
    except Exception:
        return 1

# ==== Bibliothekssteuerung (startstop.sh) ====

PROJECT_ROOT = os.path.expanduser("~/AllSkyKamera")
STARTSTOP_SH = os.path.join(PROJECT_ROOT, "startstop.sh")

def _run_startstop(arg: str) -> int:
    """
    Ruft startstop.sh mit 'start' oder 'stop' auf.
    Falls nicht executable, wird /bin/bash verwendet.
    """
    if not os.path.isfile(STARTSTOP_SH):
        return 1
    cmd = []
    if os.access(STARTSTOP_SH, os.X_OK):
        cmd = [STARTSTOP_SH, arg]
    else:
        cmd = ["/bin/bash", STARTSTOP_SH, arg]
    try:
        return subprocess.call(cmd, cwd=PROJECT_ROOT)
    except Exception:
        return 1

def cmd_lib_start():
    return _run_startstop("start")

def cmd_lib_stop():
    return _run_startstop("stop")


# ==== desired_config anwenden (Stub) ====

def apply_desired_config(ctl):
    """
    Wende gewuenschte Config-aenderungen an.
    (Derzeit Dummy — kann spaeter config.py oder config.json modifizieren)
    """
    desired = ctl.get("desired_config") or {}
    applied = {}
    success = True
    for key in ("KAMERA_NAME", "STANDORT_NAME", "LATITUDE", "LONGITUDE"):
        if key in desired:
            applied[key] = desired[key]
    return {"success": success, "details": applied}


# ==== Queue abarbeiten ====

def process_queue(ctl):
    results = []
    all_ok = True
    pending_reboot = False
    queue = ctl.get("queue") or []
    now = int(time.time())

    for item in queue:
        if item.get("processed"):
            results.append({"id": item.get("id"), "ok": True, "skipped": True})
            continue

        t = item.get("type")
        rc = 0
        ok = True

        if t == "upload_last_batch":
            rc = cmd_upload_last_batch()
            ok = (rc == 0)

        elif t == "upload_config":
            rc = cmd_upload_config()
            ok = (rc == 0)

        elif t == "lib_start":
            rc = cmd_lib_start()
            ok = (rc == 0)

        elif t == "lib_stop":
            rc = cmd_lib_stop()
            ok = (rc == 0)

        elif t == "reboot":
            pending_reboot = True
            rc = 0
            ok = True

        else:
            rc = 1
            ok = False

        item["processed"] = True
        item["processed_at"] = now
        item["result"] = {"rc": rc}
        results.append({"id": item.get("id"), "type": t, "ok": ok, "rc": rc})

        if not ok:
            all_ok = False

    if pending_reboot:
        ctl["_pending_reboot"] = True

    return {"success": all_ok, "results": results}


# ==== Hauptdurchlauf (einmaliger Cron-Run) ====

def main_loop():
    try:
        ftp = ftp_connect()

        # --- Cronmodus: Nur EIN Durchlauf ---
        if not ftp_try_lock(ftp):
            # Keine control.json gefunden → sofort beenden
            try:
                ftp.quit()
            except Exception:
                pass
            return 0

        # Datei geladen
        try:
            raw = ftp_download(ftp, PROC_NAME)
            ctl = json.loads(raw.decode("utf-8"))
        except Exception:
            ftp_delete_safe(ftp, PROC_NAME)
            ftp_delete_safe(ftp, SRC_NAME)
            ftp.quit()
            return 0

        # desired_config anwenden
        cfg_res = apply_desired_config(ctl)

        # queue verarbeiten
        q_res = process_queue(ctl)

        # Status anhaengen
        now = int(time.time())
        ctl["updated_at"] = now
        ctl["status"] = {
            "hostname": socket.gethostname(),
            "ts": now,
            "config": cfg_res,
            "queue": q_res
        }

        everything_ok = cfg_res.get("success", False) and q_res.get("success", False)

        if everything_ok:
            ftp_delete_safe(ftp, PROC_NAME)
            ftp_delete_safe(ftp, SRC_NAME)
        else:
            try:
                ftp_upload_bytes(ftp, ERR_NAME, json.dumps(ctl, indent=2).encode("utf-8"))
            except Exception:
                pass
            ftp_delete_safe(ftp, PROC_NAME)
            ftp_delete_safe(ftp, SRC_NAME)

        do_reboot = everything_ok and ctl.get("_pending_reboot") is True

        try:
            ftp.quit()
        except Exception:
            pass

        if do_reboot:
            os.sync()
            run_cmd(["/usr/bin/sudo", "/sbin/reboot"])
            return 0

        # Kein Dauerlauf, einfach beenden
        return 0

    except Exception:
        # Fehler (Netzwerk, FTP etc.) → einfach beenden, Cron startet neu
        return 0


if __name__ == "__main__":
    main_loop()
