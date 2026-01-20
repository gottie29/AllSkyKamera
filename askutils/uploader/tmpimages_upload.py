# askutils/uploader/tmpimages_upload.py

from __future__ import annotations

import argparse
import ftplib
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from askutils import config


# ---------------------------------
# Settings / Helpers
# ---------------------------------

# Unterstützt beide Formate:
# - image-YYYYMMDD_HHMMSS.jpg
# - image-YYYYMMDDHHMMSS.jpg   (dein aktuelles Format)
_TS_RE = re.compile(r"^image-(\d{8})(?:_(\d{6})|(\d{6}))\.(jpg|jpeg|png)$", re.IGNORECASE)


def _parse_date(date_yyyymmdd: str) -> datetime:
    try:
        return datetime.strptime(date_yyyymmdd, "%Y%m%d")
    except ValueError:
        raise SystemExit("Datum muss Format YYYYMMDD haben, z.B. 20260119")


def _parse_hhmm(t: str) -> tuple[int, int]:
    try:
        hh, mm = t.split(":")
        h = int(hh)
        m = int(mm)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
        return h, m
    except Exception:
        raise SystemExit("Zeit muss Format HH:MM haben, z.B. 21:00 oder 02:00")


def _compute_range(date_yyyymmdd: str, start_hhmm: str, end_hhmm: str) -> tuple[datetime, datetime]:
    base = _parse_date(date_yyyymmdd)
    sh, sm = _parse_hhmm(start_hhmm)
    eh, em = _parse_hhmm(end_hhmm)

    start_dt = base.replace(hour=sh, minute=sm, second=0)
    end_dt = base.replace(hour=eh, minute=em, second=0)

    # Wenn Endzeit "kleiner/gleich" Startzeit ist -> über Mitternacht (nächster Tag)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)

    return start_dt, end_dt


def _local_images_root() -> Path:
    """
    In deinem Screenshot: /home/pi/allsky/images/YYYYMMDD/...
    Wir versuchen:
      1) config.ALLSKY_PATH/images
      2) fallback /home/pi/allsky/images
    """
    p1 = Path(getattr(config, "ALLSKY_PATH", "/home/pi/allsky")) / "images"
    if p1.is_dir():
        return p1
    return Path("/home/pi/allsky/images")


def _iter_matching_files(root: Path, start_dt: datetime, end_dt: datetime) -> list[Path]:
    """
    Sucht Dateien vom Typ:
      image-YYYYMMDD_HHMMSS.jpg/png
      image-YYYYMMDDHHMMSS.jpg/png
    in den Tagesordnern, die im Intervall liegen.
    """
    results: list[tuple[datetime, Path]] = []

    day = start_dt.date()
    while day <= end_dt.date():
        day_dir = root / day.strftime("%Y%m%d")
        if day_dir.is_dir():
            for p in day_dir.iterdir():
                if not p.is_file():
                    continue
                m = _TS_RE.match(p.name)
                if not m:
                    continue

                d_str = m.group(1)
                t_str = m.group(2) or m.group(3)  # HHMMSS (mit oder ohne _)
                try:
                    ts = datetime.strptime(d_str + t_str, "%Y%m%d%H%M%S")
                except ValueError:
                    continue

                if start_dt <= ts <= end_dt:
                    results.append((ts, p))

        day += timedelta(days=1)

    results.sort(key=lambda x: x[0])
    return [p for _, p in results]


def _ftp_ensure_dir(ftp: ftplib.FTP, dirname: str) -> None:
    """
    Stellt sicher, dass dirname im aktuellen Verzeichnis existiert.
    """
    try:
        ftp.mkd(dirname)
    except ftplib.error_perm as e:
        # "550 File exists" o.ä. ignorieren
        msg = str(e).lower()
        if "exist" in msg or "file exists" in msg or "550" in msg:
            return
        raise


def _ftp_upload_file(ftp: ftplib.FTP, local_path: Path, remote_name: str) -> None:
    """
    Upload atomar-ish: erst .tmp dann rename.
    """
    tmp_name = remote_name + ".tmp"

    with local_path.open("rb") as f:
        ftp.storbinary(f"STOR {tmp_name}", f)

    try:
        ftp.rename(tmp_name, remote_name)
    except ftplib.error_perm:
        try:
            ftp.delete(tmp_name)
        except Exception:
            pass
        raise


# ---------------------------------
# Main Upload
# ---------------------------------

@dataclass
class UploadResult:
    total_found: int
    uploaded: int
    failed: int
    skipped: int


def upload_tmpimages(date_yyyymmdd: str, start_hhmm: str, end_hhmm: str) -> UploadResult:
    start_dt, end_dt = _compute_range(date_yyyymmdd, start_hhmm, end_hhmm)

    root = _local_images_root()
    files = _iter_matching_files(root, start_dt, end_dt)

    print(f"Range: {start_dt} -> {end_dt}")
    print(f"Lokales Archiv: {root}")
    print(f"Gefundene Dateien: {len(files)}")

    if not files:
        return UploadResult(total_found=0, uploaded=0, failed=0, skipped=0)

    uploaded = 0
    failed = 0
    skipped = 0

    # Remote: FTP_REMOTE_DIR/tmpimages
    remote_base = getattr(config, "FTP_REMOTE_DIR", None)
    if not remote_base:
        raise SystemExit("config.FTP_REMOTE_DIR fehlt (z.B. 'ASK001' oder '/ASK001' oder ähnliches).")

    with ftplib.FTP(getattr(config, "FTP_SERVER")) as ftp:
        ftp.login(getattr(config, "FTP_USER"), getattr(config, "FTP_PASS"))
        ftp.cwd(remote_base)

        # ensure tmpimages
        _ftp_ensure_dir(ftp, "tmpimages")
        ftp.cwd("tmpimages")

        for p in files:
            remote_name = p.name
            try:
                _ftp_upload_file(ftp, p, remote_name)
                uploaded += 1
                print(f"OK  {remote_name}")
            except Exception as e:
                failed += 1
                print(f"FAIL {remote_name}: {e}")

    return UploadResult(total_found=len(files), uploaded=uploaded, failed=failed, skipped=skipped)


def upload_tmpimages_cli() -> None:
    parser = argparse.ArgumentParser(
        description="Upload Bilder eines Zeitbereichs in FTP/tmpimages (letzte Nacht etc.)"
    )
    parser.add_argument("date", help="Datum YYYYMMDD, z.B. 20260119")
    parser.add_argument("start", help="Startzeit HH:MM, z.B. 21:00")
    parser.add_argument("end", help="Endzeit HH:MM, z.B. 02:00 (kann naechster Tag sein)")

    args = parser.parse_args()

    res = upload_tmpimages(args.date, args.start, args.end)
    print(f"\nSummary: found={res.total_found} uploaded={res.uploaded} failed={res.failed} skipped={res.skipped}")

    sys.exit(0 if res.failed == 0 else 2)
