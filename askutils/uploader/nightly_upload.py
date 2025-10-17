import os
import sys
import time
import ftplib
from datetime import datetime, timedelta
from askutils import config

# === Konfigurierbare Defaults ===
MIN_FILE_AGE_MINUTES   = getattr(config, "NIGHTLY_MIN_FILE_AGE_MINUTES", 5)
STABLE_WINDOW_SECONDS  = getattr(config, "NIGHTLY_STABLE_WINDOW_SECONDS", 90)
MAX_RETRIES            = getattr(config, "NIGHTLY_MAX_RETRIES", 5)
RETRY_SLEEP_SECONDS    = getattr(config, "NIGHTLY_RETRY_SLEEP_SECONDS", 600)

def log(msg: str):
    """Einfache Logfunktion mit Zeitstempel, ohne Farben."""
    t = datetime.now().strftime("%H:%M:%S")
    print(f"[{t}] {msg}", flush=True)

# === Helper ===
def _is_age_ok(path: str, min_minutes: int) -> bool:
    try:
        mtime = os.path.getmtime(path)
    except FileNotFoundError:
        return False
    age_minutes = (time.time() - mtime) / 60.0
    return age_minutes >= min_minutes

def _is_size_stable(path: str, window_sec: int, poll_sec: int = 5) -> bool:
    """
    Prueft, ob die Dateigroesse ueber window_sec stabil bleibt.
    Pollt alle poll_sec Sekunden und loggt Fortschritt.
    Startet das Fenster neu, wenn die Groesse sich aendert.
    """
    if window_sec <= 0:
        return os.path.getsize(path) > 0

    try:
        last = os.path.getsize(path)
    except FileNotFoundError:
        return False

    if last <= 0:
        log("Groesse ist 0 Byte, warte auf Daten ...")

    log(f"Stabilitaets-Check gestartet: {window_sec}s Beobachtungsfenster, Poll alle {poll_sec}s")
    start = time.time()
    stable_start = start

    while True:
        time.sleep(min(poll_sec, max(1, window_sec)))
        try:
            now_size = os.path.getsize(path)
        except FileNotFoundError:
            log("Datei waehrend Pruefung verschwunden.")
            return False

        if now_size != last:
            log(f"Groesse geaendert: {last} -> {now_size} Bytes. Beobachtungsfenster neu starten.")
            last = now_size
            stable_start = time.time()

        elapsed = time.time() - stable_start
        remaining = max(0, window_sec - int(elapsed))
        log(f"Stabil fuer {int(elapsed)}s, noch {remaining}s ... (aktuell {now_size} Bytes)")

        if elapsed >= window_sec and now_size > 0:
            log("Datei ist groessenstabil.")
            return True

def _file_ready(path: str) -> bool:
    """Nur Alter und Groessenstabilitaet pruefen."""
    if not os.path.isfile(path):
        return False
    if not _is_age_ok(path, MIN_FILE_AGE_MINUTES):
        return False
    if not _is_size_stable(path, STABLE_WINDOW_SECONDS):
        return False
    return True

def _upload_file(ftp: ftplib.FTP, local_path: str, remote_subdir: str, root_dir: str):
    """Atomic Upload: erst temporaer, dann rename auf Zielname."""
    try:
        ftp.cwd(remote_subdir)
    except ftplib.error_perm:
        log(f"Remote-Verzeichnis '{remote_subdir}' nicht vorhanden, wird erstellt ...")
        ftp.mkd(remote_subdir)
        ftp.cwd(remote_subdir)

    base = os.path.basename(local_path)
    tmp_name = f".{base}.uploading"

    log(f"Starte Upload: {local_path} -> /{root_dir}/{remote_subdir}/{base}")
    with open(local_path, "rb") as f:
        ftp.storbinary(f"STOR {tmp_name}", f)

    try:
        ftp.rename(tmp_name, base)
    except Exception:
        try:
            ftp.delete(tmp_name)
        except Exception:
            pass
        raise

    log(f"Upload abgeschlossen: {base} -> /{remote_subdir}")
    ftp.cwd("..")

def upload_nightly_batch(date_str: str = None) -> bool:
    """
    Laedt Video, Keogram, Startrail und Analemma-Dateien per FTP hoch.
    Nutzt Alters- und Stabilitaets-Checks mit detaillierten Statusmeldungen.
    """
    if date_str is None:
        date_str = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    log(f"Starte Nightly Upload fuer {date_str}")

    images_base   = os.path.join(config.ALLSKY_PATH, config.IMAGE_BASE_PATH)
    analemma_base = os.path.join(config.A_PATH)

    files = [
        (os.path.join(images_base, date_str, f"allsky-{date_str}.mp4"),          config.FTP_VIDEO_DIR),
        (os.path.join(images_base, date_str, "keogram",   f"keogram-{date_str}.jpg"),    config.FTP_KEOGRAM_DIR),
        (os.path.join(images_base, date_str, "startrails",f"startrails-{date_str}.jpg"), config.FTP_STARTRAIL_DIR),
        (os.path.join(analemma_base, f"analemma-{date_str}_used.jpg"),           config.FTP_ANALEMMA_DIR),
        (os.path.join(analemma_base, f"analemma-{date_str}_unused.jpg"),         config.FTP_ANALEMMA_DIR),
    ]

    try:
        with ftplib.FTP(config.FTP_SERVER) as ftp:
            ftp.login(config.FTP_USER, config.FTP_PASS)
            ftp.cwd(config.FTP_REMOTE_DIR)
            log(f"Verbindung zu FTP-Server '{config.FTP_SERVER}' hergestellt.")

            for local_path, remote_subdir in files:
                log(f"Pruefe Datei: {local_path}")

                if not os.path.isfile(local_path):
                    log(f"Datei fehlt: {local_path}")
                    continue

                # bis zu MAX_RETRIES + 1 Versuche
                attempt = 0
                while attempt <= MAX_RETRIES and not _file_ready(local_path):
                    if attempt == MAX_RETRIES:
                        log(f"Uebersprungen (nicht bereit): {local_path}")
                        break
                    wait = RETRY_SLEEP_SECONDS * (attempt + 1)
                    log(f"Noch nicht bereit ({attempt+1}/{MAX_RETRIES+1}), erneuter Versuch in {wait}s ...")
                    time.sleep(wait)
                    attempt += 1

                if attempt <= MAX_RETRIES and _file_ready(local_path):
                    log("Datei bereit, starte Upload ...")
                    try:
                        _upload_file(ftp, local_path, remote_subdir, config.FTP_REMOTE_DIR)
                    except Exception as e:
                        log(f"Upload-Fehler fuer {local_path}: {e}")

            log("Nightly Upload abgeschlossen.")
        return True

    except Exception as e:
        log(f"Batch-FTP-Upload fehlgeschlagen: {e}")
        return False
