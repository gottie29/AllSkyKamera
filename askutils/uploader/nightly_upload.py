import os
import sys
import time
import glob
import ftplib
import tempfile
from datetime import datetime, timedelta
from askutils import config
from typing import Optional, List, Tuple

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

def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")

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

def _choose_newest_existing(*candidates: str) -> Optional[str]:
    """Wenn mehrere Kandidaten existieren (jpg/png), nimm die neueste Datei (mtime)."""
    files = [p for p in candidates if p and os.path.isfile(p)]
    if not files:
        return None
    return max(files, key=lambda p: os.path.getmtime(p))

def _png_to_temp_jpg_named(png_path: str) -> str:
    """
    PNG -> temporäres JPG konvertieren.
    Der Temp-Name orientiert sich am Originalnamen (wichtig fürs spätere Remote-Rename-Handling).
    Alpha wird auf schwarz geflattet.
    """
    try:
        from PIL import Image
    except ImportError as e:
        raise RuntimeError("Pillow fehlt. Installiere mit: pip install pillow") from e

    base_noext = os.path.splitext(os.path.basename(png_path))[0]
    fd, tmp_path = tempfile.mkstemp(prefix=f"{base_noext}_", suffix=".jpg")
    os.close(fd)

    img = Image.open(png_path)

    if img.mode in ("RGBA", "LA") or ("transparency" in getattr(img, "info", {})):
        img = img.convert("RGBA")
        bg = Image.new("RGBA", img.size, (0, 0, 0, 255))
        img = Image.alpha_composite(bg, img).convert("RGB")
    else:
        img = img.convert("RGB")

    img.save(tmp_path, format="JPEG", quality=90, optimize=True)
    return tmp_path

def _ensure_uploadable_jpg(local_path: str) -> Tuple[str, Optional[str]]:
    """
    Stellt sicher, dass für Bilder nur JPG hochgeladen wird.
    - wenn local_path .jpg => unverändert
    - wenn local_path .png => in temp-jpg konvertieren und (upload_path, temp_path) zurückgeben
    """
    ext = os.path.splitext(local_path)[1].lower()
    if ext == ".png":
        tmp = _png_to_temp_jpg_named(local_path)
        return tmp, tmp
    return local_path, None

def _upload_file_as(ftp: ftplib.FTP, local_path: str, remote_subdir: str, root_dir: str, remote_base_name: str):
    """
    Atomic Upload: erst temporaer, dann rename auf Zielname.
    remote_base_name bestimmt den finalen Dateinamen (z.B. "... .jpg").
    """
    try:
        ftp.cwd(remote_subdir)
    except ftplib.error_perm:
        log(f"Remote-Verzeichnis '{remote_subdir}' nicht vorhanden, wird erstellt ...")
        ftp.mkd(remote_subdir)
        ftp.cwd(remote_subdir)

    tmp_name = f".{remote_base_name}.uploading"

    log(f"Starte Upload: {local_path} -> /{root_dir}/{remote_subdir}/{remote_base_name}")
    with open(local_path, "rb") as f:
        ftp.storbinary(f"STOR {tmp_name}", f)

    try:
        ftp.rename(tmp_name, remote_base_name)
    except Exception:
        try:
            ftp.delete(tmp_name)
        except Exception:
            pass
        raise

    log(f"Upload abgeschlossen: {remote_base_name} -> /{remote_subdir}")
    ftp.cwd("..")

def _remote_name_for(local_path: str, date_str: str, *, for_startrail_video: bool = False) -> Optional[str]:
    """
    Zielname nach Typ-Regel.
    - Für Videos (mp4/webm): Endung beibehalten.
    - for_startrail_video=True: startrail_timelapse -> startrail_timelapse-<date>.<ext>
    - Für Bilder: immer .jpg remote (auch wenn Quelle .png war)
    """
    base = os.path.basename(local_path)
    low  = base.lower()
    ext  = os.path.splitext(low)[1]  # ".mp4" ".webm" ".jpg" ".png"

    # Startrail-Timelapse Video (INDI extra)
    if for_startrail_video and ext in (".mp4", ".webm") and "startrail_timelapse" in low:
        return f"startrail_timelapse-{date_str}{ext}"

    # Bilder: akzeptiere .jpg oder .png, remote immer .jpg
    if ext in (".jpg", ".png") and "startrail" in low:
        return f"startrails-{date_str}.jpg"
    if ext in (".jpg", ".png") and "keogram" in low:
        return f"keogram-{date_str}.jpg"
    if ext in (".jpg", ".png") and "analemma" in low:
        # bleibt wie bisher (deine Dateien heissen analemma-<date>_used/unused.*)
        # -> wir lassen den Namen später unten direkt aus dem Dateinamen ableiten (siehe Analemma-Handling)
        return None

    # Haupt-Timelapse (mp4/webm)
    if ext in (".mp4", ".webm") and ("timelapse" in low or "allsky" in low):
        return f"allsky-{date_str}{ext}"

    return None

def upload_nightly_batch(date_str: str = None) -> bool:
    """
    Laedt Video, Keogram, Startrail, Startrail-Timelapse (nur INDI) und Analemma-Dateien per FTP hoch.
    Nutzt Alters- und Stabilitaets-Checks mit detaillierten Statusmeldungen.

    PNG Handling:
      - Keogram/Startrail/Analemma dürfen lokal .png oder .jpg sein
      - PNG wird lokal temp -> JPG konvertiert
      - nur JPG wird hochgeladen, temp-JPG wird danach gelöscht
    """
    if date_str is None:
        date_str = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    log(f"Starte Nightly Upload fuer {date_str}")

    images_base   = os.path.join(config.ALLSKY_PATH, config.IMAGE_BASE_PATH)
    analemma_base = os.path.join(config.A_PATH)

    indi_flag = _truthy(getattr(config, "INDI", 0))

    # Dateienliste: (local_path, remote_subdir, forced_remote_name_or_None)
    files: List[Tuple[Optional[str], str, Optional[str]]] = []

    if not indi_flag:
        # Video kann mp4 oder webm sein
        mp4_path  = os.path.join(images_base, date_str, f"allsky-{date_str}.mp4")
        webm_path = os.path.join(images_base, date_str, f"allsky-{date_str}.webm")
        video = mp4_path if os.path.isfile(mp4_path) else (webm_path if os.path.isfile(webm_path) else None)

        # Keogram/Startrail können jpg oder png sein -> neueste gewinnt
        keo_jpg = os.path.join(images_base, date_str, "keogram",    f"keogram-{date_str}.jpg")
        keo_png = os.path.join(images_base, date_str, "keogram",    f"keogram-{date_str}.png")
        st_jpg  = os.path.join(images_base, date_str, "startrails", f"startrails-{date_str}.jpg")
        st_png  = os.path.join(images_base, date_str, "startrails", f"startrails-{date_str}.png")

        keo = _choose_newest_existing(keo_jpg, keo_png)
        st  = _choose_newest_existing(st_jpg, st_png)

        # Analemma optional (.jpg oder .png)
        a_used_jpg   = os.path.join(analemma_base, f"analemma-{date_str}_used.jpg")
        a_used_png   = os.path.join(analemma_base, f"analemma-{date_str}_used.png")
        a_unused_jpg = os.path.join(analemma_base, f"analemma-{date_str}_unused.jpg")
        a_unused_png = os.path.join(analemma_base, f"analemma-{date_str}_unused.png")

        a_used   = _choose_newest_existing(a_used_jpg, a_used_png)
        a_unused = _choose_newest_existing(a_unused_jpg, a_unused_png)

        if video: files.append((video, config.FTP_VIDEO_DIR, None))
        if keo:   files.append((keo,   config.FTP_KEOGRAM_DIR, f"keogram-{date_str}.jpg"))
        if st:    files.append((st,    config.FTP_STARTRAIL_DIR, f"startrails-{date_str}.jpg"))
        if a_used:
            files.append((a_used, config.FTP_ANALEMMA_DIR, os.path.basename(a_used).replace(".png", ".jpg")))
        if a_unused:
            files.append((a_unused, config.FTP_ANALEMMA_DIR, os.path.basename(a_unused).replace(".png", ".jpg")))

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

        # Keogram / Startrail: jpg oder png
        keo = _latest_multi([
            os.path.join(date_dir, f"allsky-keogram_*_{date_str}_night_*.jpg"),
            os.path.join(date_dir, f"allsky-keogram_*_{date_str}_night_*.png"),
        ])
        st  = _latest_multi([
            os.path.join(date_dir, f"allsky-startrail_*_{date_str}_night_*.jpg"),
            os.path.join(date_dir, f"allsky-startrail_*_{date_str}_night_*.png"),
        ])

        # Timelapse (Standard) -> VIDEO_DIR (mp4 oder webm)
        tl = _latest_multi([
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
            f"timelapse={os.path.basename(tl) if tl else '-'}, "
            f"startrail_video={os.path.basename(stv) if stv else '-'}"
        )

        startrailsvideo_dir = getattr(config, "FTP_STARTRAILSVIDEO_DIR", "startrailsvideo")

        if tl:  files.append((tl,  config.FTP_VIDEO_DIR, None))
        if keo: files.append((keo, config.FTP_KEOGRAM_DIR, f"keogram-{date_str}.jpg"))
        if st:  files.append((st,  config.FTP_STARTRAIL_DIR, f"startrails-{date_str}.jpg"))
        if stv: files.append((stv, startrailsvideo_dir, None))

        # Analemma optional (.jpg oder .png)
        a_used_jpg   = os.path.join(analemma_base, f"analemma-{date_str}_used.jpg")
        a_used_png   = os.path.join(analemma_base, f"analemma-{date_str}_used.png")
        a_unused_jpg = os.path.join(analemma_base, f"analemma-{date_str}_unused.jpg")
        a_unused_png = os.path.join(analemma_base, f"analemma-{date_str}_unused.png")

        a_used   = _choose_newest_existing(a_used_jpg, a_used_png)
        a_unused = _choose_newest_existing(a_unused_jpg, a_unused_png)

        if a_used:
            files.append((a_used, config.FTP_ANALEMMA_DIR, os.path.basename(a_used).replace(".png", ".jpg")))
        if a_unused:
            files.append((a_unused, config.FTP_ANALEMMA_DIR, os.path.basename(a_unused).replace(".png", ".jpg")))

    try:
        with ftplib.FTP(config.FTP_SERVER) as ftp:
            ftp.login(config.FTP_USER, config.FTP_PASS)
            ftp.cwd(config.FTP_REMOTE_DIR)
            log(f"Verbindung zu FTP-Server hergestellt.")

            for local_path, remote_subdir, forced_remote_name in files:
                log(f"Pruefe Datei: {local_path}")

                if not local_path or not os.path.isfile(local_path):
                    log(f"Datei fehlt: {local_path}")
                    continue

                # bis zu MAX_RETRIES + 1 Versuche (auf ORIGINALDATEI prüfen!)
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

                    # Für Bilder ggf. PNG->JPG (temp). Videos bleiben unverändert.
                    upload_path = local_path
                    temp_jpg = None
                    ext = os.path.splitext(local_path)[1].lower()
                    try:
                        if ext in (".jpg", ".png"):
                            upload_path, temp_jpg = _ensure_uploadable_jpg(local_path)

                        # Remote Name: bei Bildern erzwingen wir .jpg (forced_remote_name),
                        # bei Videos bleibt Original (und ggf. späterer Rename durch dein Schema).
                        remote_base = forced_remote_name if forced_remote_name else os.path.basename(upload_path)

                        _upload_file_as(ftp, upload_path, remote_subdir, config.FTP_REMOTE_DIR, remote_base)

                        # Optional: Remote-Rename für Videos nach deinem bestehenden Schema
                        # (Bilder laden wir schon unter finalem Namen hoch -> kein Rename nötig)
                        lp = os.path.basename(local_path).lower()
                        is_startrail_video = lp.endswith((".mp4", ".webm")) and \
                                             "startrail_timelapse" in lp and \
                                             _truthy(getattr(config, "INDI", 0))

                        if os.path.splitext(lp)[1] in (".mp4", ".webm"):
                            desired = _remote_name_for(local_path, date_str, for_startrail_video=is_startrail_video)
                            if desired:
                                try:
                                    prev = ftp.pwd()
                                    ftp.cwd(remote_subdir)

                                    src = os.path.basename(upload_path)  # hochgeladen unter diesem Namen
                                    if src != desired:
                                        log(f"Rename remote: {src} -> {desired}")
                                        try:
                                            ftp.rename(src, desired)
                                        except ftplib.error_perm:
                                            try:
                                                ftp.delete(desired)
                                                ftp.rename(src, desired)
                                            except Exception as e2:
                                                log(f"Rename/Replace fehlgeschlagen: {e2}")

                                    ftp.cwd(prev)
                                except Exception as e:
                                    log(f"Remote-Rename fehlgeschlagen ({local_path}): {e}")

                    except Exception as e:
                        log(f"Upload-Fehler fuer {local_path}: {e}")
                    finally:
                        # Temp-JPG nach Upload/Fehler wieder löschen
                        if temp_jpg and os.path.isfile(temp_jpg):
                            try:
                                os.remove(temp_jpg)
                            except Exception:
                                pass

            log("Nightly Upload abgeschlossen.")
        return True

    except Exception as e:
        log(f"Batch-FTP-Upload fehlgeschlagen: {e}")
        return False
