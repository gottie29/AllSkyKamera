import os
import glob
import ftplib
import tempfile
from datetime import datetime
from typing import Optional, List, Tuple
from askutils import config


def log(msg: str) -> None:
    """Einfache Logfunktion mit Zeitstempel, ohne Farben."""
    t = datetime.now().strftime("%H:%M:%S")
    print(f"[{t}] {msg}", flush=True)


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


def _upload_file_as(ftp: ftplib.FTP, local_path: str, remote_subdir: str, root_dir: str, remote_base_name: str) -> None:
    """Atomic Upload: erst temporaer, dann rename auf Zielname (remote_base_name)."""
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
    - Für Bilder: remote immer .jpg (auch wenn Quelle .png war)
    """
    base = os.path.basename(local_path)
    low  = base.lower()
    ext  = os.path.splitext(low)[1]  # ".mp4" ".webm" ".jpg" ".png"

    if for_startrail_video and ext in (".mp4", ".webm") and "startrail_timelapse" in low:
        return f"startrail_timelapse-{date_str}{ext}"

    if ext in (".jpg", ".png") and "startrail" in low:
        return f"startrails-{date_str}.jpg"
    if ext in (".jpg", ".png") and "keogram" in low:
        return f"keogram-{date_str}.jpg"

    if ext in (".mp4", ".webm") and ("timelapse" in low or "allsky" in low):
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
    Unterstützt PNG/JPG (Bilder werden immer als JPG hochgeladen; PNG->JPG temp).
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

    # Dateienliste: (local_path, remote_subdir, forced_remote_name_or_None)
    files: List[Tuple[Optional[str], str, Optional[str]]] = []

    if not indi_flag:
        # Klassischer Pfad (nicht INDI): Video kann mp4 oder webm sein
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

        if video:   files.append((video, config.FTP_VIDEO_DIR, None))
        if keo:     files.append((keo,   config.FTP_KEOGRAM_DIR,   f"keogram-{date_str}.jpg"))
        if st:      files.append((st,    config.FTP_STARTRAIL_DIR, f"startrails-{date_str}.jpg"))
        if a_used:  files.append((a_used,   config.FTP_ANALEMMA_DIR, f"analemma-{date_str}_used.jpg"))
        if a_unused:files.append((a_unused, config.FTP_ANALEMMA_DIR, f"analemma-{date_str}_unused.jpg"))

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

        startrailsvideo_dir = getattr(config, "FTP_STARTRAILSVIDEO_DIR", "startrailsvideo")

        if mp4: files.append((mp4, config.FTP_VIDEO_DIR, None))
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

        if a_used:   files.append((a_used,   config.FTP_ANALEMMA_DIR, f"analemma-{date_str}_used.jpg"))
        if a_unused: files.append((a_unused, config.FTP_ANALEMMA_DIR, f"analemma-{date_str}_unused.jpg"))

    try:
        with ftplib.FTP(config.FTP_SERVER) as ftp:
            ftp.login(config.FTP_USER, config.FTP_PASS)
            ftp.cwd(config.FTP_REMOTE_DIR)
            log(f"Verbindung zu FTP-Server '{config.FTP_SERVER}' hergestellt.")

            for local_path, remote_subdir, forced_remote_name in files:
                log(f"Pruefe Datei: {local_path}")

                if not local_path or not _file_available(local_path):
                    log(f"Datei fehlt oder ist leer, uebersprungen: {local_path}")
                    continue

                temp_jpg = None
                upload_path = local_path
                try:
                    ext = os.path.splitext(local_path)[1].lower()
                    if ext in (".jpg", ".png"):
                        upload_path, temp_jpg = _ensure_uploadable_jpg(local_path)

                    remote_base = forced_remote_name if forced_remote_name else os.path.basename(upload_path)

                    try:
                        _upload_file_as(ftp, upload_path, remote_subdir, config.FTP_REMOTE_DIR, remote_base)
                    except Exception as e:
                        log(f"Upload-Fehler fuer {local_path}: {e}")
                        continue

                    # Video-Rename nach deinem Schema (Bilder wurden schon final benannt)
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

                                src = os.path.basename(upload_path)
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

                finally:
                    if temp_jpg and os.path.isfile(temp_jpg):
                        try:
                            os.remove(temp_jpg)
                        except Exception:
                            pass

            log("Manueller Upload abgeschlossen.")
        return True

    except Exception as e:
        log(f"Batch-FTP-Upload fehlgeschlagen: {e}")
        return False
