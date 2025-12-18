import os
import sys
import time
import glob
import ftplib
from datetime import datetime, timedelta
from askutils import config
from typing import Optional, List

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
    stable_start = time.time()

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
    """Atomic Upload: erst temporaer, dann rename auf Zielname (Originalname)."""
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

def _latest(glob_pattern: str) -> Optional[str]:
    """Neueste Datei zum Muster."""
    cand = glob.glob(glob_pattern)
    if not cand:
        return None
    cand.sort(key=lambda p: os.path.getmtime(p))
    return cand[-1]

def _latest_multi(patterns: List[str]) -> Optional[str]:
    """Neueste Datei über mehrere Glob-Patterns hinweg."""
    all_files = []
    for pat in patterns:
        all_files.extend(glob.glob(pat))
    if not all_files:
        return None
    all_files.sort(key=lambda p: os.path.getmtime(p))
    return all_files[-1]

def _remote_name_for(local_path: str, date_str: str, *, for_startrail_video: bool = False) -> Optional[str]:
    """
    Zielname nach Typ-Regel.
    - Für Videos (mp4/webm): Endung beibehalten.
    - for_startrail_video=True: startrail_timelapse -> startrail_timelapse-<date>.<ext>
    """
    base = os.path.basename(local_path)
    low  = base.lower()
    ext  = os.path.splitext(low)[1]  # ".mp4" oder ".webm" etc.

    # Startrail-Timelapse Video (INDI extra)
    if for_startrail_video and ext in (".mp4", ".webm") and "startrail_timelapse" in low:
        return f"startrail_timelapse-{date_str}{ext}"

    # Bilder
    if low.endswith(".jpg") and "startrail" in low:
        return f"startrails-{date_str}.jpg"
    if low.endswith(".jpg") and "keogram" in low:
        return f"keogram-{date_str}.jpg"

    # Haupt-Timelapse (mp4/webm)
    if ext in (".mp4", ".webm") and ("timelapse" in low or "allsky" in low):
        # Achtung: startrail_timelapse wird oben separat behandelt.
        return f"allsky-{date_str}{ext}"

    return None

def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")

def upload_nightly_batch(date_str: str = None) -> bool:
    """
    Laedt Video, Keogram, Startrail, Startrail-Timelapse (nur INDI) und Analemma-Dateien per FTP hoch.
    Nutzt Alters- und Stabilitaets-Checks mit detaillierten Statusmeldungen.

    INDI:
      - nutzt CAMERAID aus config.py (z.B. "ccd_....")
      - nimmt Dateien unter:
        <images_base>/<CAMERAID>/timelapse/<YYYYMMDD>/
      - waehlt die jeweils neueste passende Datei je Typ und benennt remote um.
      - zusaetzlich: allsky-startrail_timelapse_*.mp4/.webm -> FTP_STARTRAILSVIDEO_DIR (remote)
    """
    if date_str is None:
        date_str = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    log(f"Starte Nightly Upload fuer {date_str}")

    images_base   = os.path.join(config.ALLSKY_PATH, config.IMAGE_BASE_PATH)
    analemma_base = os.path.join(config.A_PATH)

    indi_flag = _truthy(getattr(config, "INDI", 0))

    if not indi_flag:
        # Video kann mp4 oder webm sein
        video = None
        mp4_path  = os.path.join(images_base, date_str, f"allsky-{date_str}.mp4")
        webm_path = os.path.join(images_base, date_str, f"allsky-{date_str}.webm")
        if os.path.isfile(mp4_path):
            video = mp4_path
        elif os.path.isfile(webm_path):
            video = webm_path

        files = [
            (video,                                                      config.FTP_VIDEO_DIR),
            (os.path.join(images_base, date_str, "keogram",    f"keogram-{date_str}.jpg"),    config.FTP_KEOGRAM_DIR),
            (os.path.join(images_base, date_str, "startrails", f"startrails-{date_str}.jpg"), config.FTP_STARTRAIL_DIR),
            (os.path.join(analemma_base, f"analemma-{date_str}_used.jpg"),                    config.FTP_ANALEMMA_DIR),
            (os.path.join(analemma_base, f"analemma-{date_str}_unused.jpg"),                  config.FTP_ANALEMMA_DIR),
        ]
    else:
        # === INDI: CAMERAID aus config verwenden ===
        cam_id = getattr(config, "CAMERAID", None)
        if not cam_id:
            log("INDI ist aktiv, aber config.CAMERAID ist nicht gesetzt.")
            return False

        indi_cam_dir = os.path.join(images_base, cam_id)
        if not os.path.isdir(indi_cam_dir):
            log(f"INDI Kameraordner nicht gefunden: {indi_cam_dir}")
            return False

        log(f"Verwende INDI Kameraordner (aus config.CAMERAID): {indi_cam_dir}")

        date_dir = os.path.join(indi_cam_dir, "timelapse", date_str)
        if not os.path.isdir(date_dir):
            log(f"Datumspfad fehlt: {date_dir}")

        # neueste Dateien je Typ (gemäß deiner Struktur)
        keo = _latest(os.path.join(date_dir, f"allsky-keogram_*_{date_str}_night_*.jpg"))
        st  = _latest(os.path.join(date_dir, f"allsky-startrail_*_{date_str}_night_*.jpg"))

        # Timelapse (Standard) -> VIDEO_DIR (mp4 oder webm)
        mp4 = _latest_multi([
            os.path.join(date_dir, f"allsky-timelapse_*_{date_str}_night_*.mp4"),
            os.path.join(date_dir, f"allsky-timelapse_*_{date_str}_night_*.webm"),
        ])

        # Startrail-Timelapse (zusätzlich) -> STARTRAILSVIDEO_DIR (mp4 oder webm)
        stv = _latest_multi([
            os.path.join(date_dir, f"allsky-startrail_timelapse_*_{date_str}_night_*.mp4"),
            os.path.join(date_dir, f"allsky-startrail_timelapse_*_{date_str}_night_*.webm"),
        ])

        log(
            f"Gefunden: keogram={os.path.basename(keo) if keo else '-'}, "
            f"startrail={os.path.basename(st) if st else '-'}, "
            f"timelapse={os.path.basename(mp4) if mp4 else '-'}, "
            f"startrail_video={os.path.basename(stv) if stv else '-'}"
        )

        # Zielordner auf dem Server:
        # - fuer stv brauchst du in config.py: FTP_STARTRAILSVIDEO_DIR = "startrailsvideo"
        startrailsvideo_dir = getattr(config, "FTP_STARTRAILSVIDEO_DIR", "startrailsvideo")

        files = []
        if mp4: files.append((mp4, config.FTP_VIDEO_DIR))
        if keo: files.append((keo, config.FTP_KEOGRAM_DIR))
        if st:  files.append((st,  config.FTP_STARTRAIL_DIR))
        if stv: files.append((stv, startrailsvideo_dir))

        # Analemma optional
        files.extend([
            (os.path.join(analemma_base, f"analemma-{date_str}_used.jpg"),    config.FTP_ANALEMMA_DIR),
            (os.path.join(analemma_base, f"analemma-{date_str}_unused.jpg"),  config.FTP_ANALEMMA_DIR),
        ])

    try:
        with ftplib.FTP(config.FTP_SERVER) as ftp:
            ftp.login(config.FTP_USER, config.FTP_PASS)
            ftp.cwd(config.FTP_REMOTE_DIR)
            log(f"Verbindung zu FTP-Server '{config.FTP_SERVER}' hergestellt.")

            for local_path, remote_subdir in files:
                log(f"Pruefe Datei: {local_path}")

                if not local_path or not os.path.isfile(local_path):
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
                        continue

                    # Nach dem Upload serverseitig auf Zielnamen umbenennen
                    lp = os.path.basename(local_path).lower()
                    is_startrail_video = lp.endswith((".mp4", ".webm")) and \
                                         "startrail_timelapse" in lp and \
                                         _truthy(getattr(config, "INDI", 0))

                    desired = _remote_name_for(local_path, date_str, for_startrail_video=is_startrail_video)
                    if desired:
                        try:
                            prev = ftp.pwd()
                            ftp.cwd(remote_subdir)

                            src = os.path.basename(local_path)  # _upload_file laedt unter Originalnamen hoch
                            if src != desired:
                                log(f"Rename remote: {src} -> {desired}")
                                try:
                                    ftp.rename(src, desired)
                                except ftplib.error_perm:
                                    # Falls Ziel schon existiert -> ersetzen
                                    try:
                                        ftp.delete(desired)
                                        ftp.rename(src, desired)
                                    except Exception as e2:
                                        log(f"Rename/Replace fehlgeschlagen: {e2}")

                            ftp.cwd(prev)
                        except Exception as e:
                            log(f"Remote-Rename fehlgeschlagen ({local_path}): {e}")

            log("Nightly Upload abgeschlossen.")
        return True

    except Exception as e:
        log(f"Batch-FTP-Upload fehlgeschlagen: {e}")
        return False
