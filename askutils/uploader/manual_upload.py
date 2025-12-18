import os
import glob
import ftplib
from datetime import datetime
from typing import Optional, List
from askutils import config


def log(msg: str) -> None:
    """Einfache Logfunktion mit Zeitstempel, ohne Farben."""
    t = datetime.now().strftime("%H:%M:%S")
    print(f"[{t}] {msg}", flush=True)


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _upload_file(ftp: ftplib.FTP, local_path: str, remote_subdir: str, root_dir: str) -> None:
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

    if for_startrail_video and ext in (".mp4", ".webm") and "startrail_timelapse" in low:
        return f"startrail_timelapse-{date_str}{ext}"

    if low.endswith(".jpg") and "startrail" in low:
        return f"startrails-{date_str}.jpg"
    if low.endswith(".jpg") and "keogram" in low:
        return f"keogram-{date_str}.jpg"

    if ext in (".mp4", ".webm") and ("timelapse" in low or "allsky" in low):
        # Achtung: das umfasst auch "startrail_timelapse" – daher wird das oben separat behandelt.
        return f"allsky-{date_str}{ext}"

    return None


def _file_available(path: str) -> bool:
    """Nur pruefen, ob die Datei existiert und > 0 Byte hat."""
    if not os.path.isfile(path):
        return False
    try:
        return os.path.getsize(path) > 0
    except OSError:
        return False


def upload_manual_batch(date_str: str) -> bool:
    """
    Manueller Upload fuer einen expliziten Tag (JJJJMMTT).
    Kein Alters- oder Stabilitaets-Check – nur: Datei vorhanden und > 0 Byte.
    Nutzt dieselbe Logik wie nightly_upload (inkl. INDI-Unterstuetzung),
    greift aber NICHT auf nightly_upload.py zurueck.

    INDI:
      - nutzt CAMERAID aus config.py (z.B. "ccd_....")
      - nimmt Dateien unter:
        <images_base>/<CAMERAID>/timelapse/<YYYYMMDD>/
      - zusaetzlich: allsky-startrail_timelapse_*.mp4/.webm -> FTP_STARTRAILSVIDEO_DIR (remote)
    """
    # Datum validieren
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
    except ValueError:
        log(f"Ungueltiges Datum: {date_str} (erwartet: JJJJMMTT)")
        return False

    date_str = dt.strftime("%Y%m%d")
    log(f"Starte MANUELLEN Upload fuer {date_str}")

    images_base   = os.path.join(config.ALLSKY_PATH, config.IMAGE_BASE_PATH)
    analemma_base = os.path.join(config.A_PATH)

    indi_flag = _truthy(getattr(config, "INDI", 0))

    if not indi_flag:
        # Klassischer Pfad (nicht INDI): Video kann mp4 oder webm sein
        video = None
        mp4_path  = os.path.join(images_base, date_str, f"allsky-{date_str}.mp4")
        webm_path = os.path.join(images_base, date_str, f"allsky-{date_str}.webm")
        if os.path.isfile(mp4_path):
            video = mp4_path
        elif os.path.isfile(webm_path):
            video = webm_path

        files = [
            (video,                                                       config.FTP_VIDEO_DIR),
            (os.path.join(images_base, date_str, "keogram",    f"keogram-{date_str}.jpg"),     config.FTP_KEOGRAM_DIR),
            (os.path.join(images_base, date_str, "startrails", f"startrails-{date_str}.jpg"),  config.FTP_STARTRAIL_DIR),
            (os.path.join(analemma_base, f"analemma-{date_str}_used.jpg"),                     config.FTP_ANALEMMA_DIR),
            (os.path.join(analemma_base, f"analemma-{date_str}_unused.jpg"),                   config.FTP_ANALEMMA_DIR),
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

        keo = _latest(os.path.join(date_dir, f"allsky-keogram_*_{date_str}_night_*.jpg"))
        st  = _latest(os.path.join(date_dir, f"allsky-startrail_*_{date_str}_night_*.jpg"))

        # Timelapse (mp4 oder webm)
        mp4 = _latest_multi([
            os.path.join(date_dir, f"allsky-timelapse_*_{date_str}_night_*.mp4"),
            os.path.join(date_dir, f"allsky-timelapse_*_{date_str}_night_*.webm"),
        ])

        # Startrail-Timelapse (mp4 oder webm)
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
        if mp4:
            files.append((mp4, config.FTP_VIDEO_DIR))
        if keo:
            files.append((keo, config.FTP_KEOGRAM_DIR))
        if st:
            files.append((st, config.FTP_STARTRAIL_DIR))
        if stv:
            files.append((stv, startrailsvideo_dir))

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

                if not local_path or not _file_available(local_path):
                    log(f"Datei fehlt oder ist leer, uebersprungen: {local_path}")
                    continue

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

            log("Manueller Upload abgeschlossen.")
        return True

    except Exception as e:
        log(f"Batch-FTP-Upload fehlgeschlagen: {e}")
        return False
