#!/usr/bin/env python3
import sys
import os
from datetime import datetime
from typing import Optional

from askutils.uploader.nightly_upload_tj_api import upload_nightly_batch
from askutils import config


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _parse_date_arg(arg: str) -> str:
    _log(f"Pruefe Datumsargument: {arg}")

    try:
        dt = datetime.strptime(arg, "%Y%m%d")
    except ValueError:
        _log("Fehler: Datum muss im Format JJJJMMTT angegeben werden, z.B. 20260310.")
        sys.exit(1)

    normalized = dt.strftime("%Y%m%d")
    _log(f"Datumsargument gueltig: {normalized}")
    return normalized


def _get_image_root() -> str:
    allsky_path = getattr(config, "ALLSKY_PATH", "") or ""
    image_base_path = getattr(config, "IMAGE_BASE_PATH", "") or ""

    if image_base_path:
        return os.path.join(allsky_path, image_base_path)
    return allsky_path


def _show_paths(date_str: Optional[str]) -> None:
    """
    Zeigt nur noch die aus config.py abgeleiteten Pfade an.
    """
    _log("---- Konfiguration / Pfade ----")

    try:
        kamera_id = getattr(config, "KAMERA_ID", "UNKNOWN")
        allsky_path = getattr(config, "ALLSKY_PATH", "")
        image_base_path = getattr(config, "IMAGE_BASE_PATH", "")
        image_path = getattr(config, "IMAGE_PATH", "")
        image_root = _get_image_root()

        _log(f"KAMERA_ID: {kamera_id}")
        _log(f"ALLSKY_PATH: {allsky_path}")
        _log(f"IMAGE_BASE_PATH: {image_base_path}")
        _log(f"IMAGE_PATH: {image_path}")
        _log(f"IMAGE_ROOT: {image_root}")

    except Exception as e:
        _log(f"Fehler beim Lesen der Config: {e}")
        return

    if date_str:
        _log(f"Nightly Datum: {date_str}")
    else:
        _log("Nightly Datum: automatisch (gestern)")

    try:
        paths = [image_root]

        if date_str:
            paths.extend([
                os.path.join(image_root, date_str),
                os.path.join(image_root, date_str, "keogram"),
                os.path.join(image_root, date_str, "startrails"),
                os.path.join(image_root, date_str, "videos"),
            ])

        _log("---- Abgeleitete Dateipfade ----")
        for p in paths:
            exists = "OK" if os.path.exists(p) else "MISSING"
            _log(f"{exists}  {p}")

    except Exception as e:
        _log(f"Pfade konnten nicht geprueft werden: {e}")

    _log("-----------------------------")


def main() -> None:
    _log("Starte run_nightly_upload_tj_api")

    if len(sys.argv) > 2 or (len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help")):
        print(
            "Verwendung:\n"
            "  python3 -m scripts.run_nightly_upload_tj_api\n"
            "    -> laedt die letzte Nacht (gestern) hoch\n\n"
            "  python3 -m scripts.run_nightly_upload_tj_api 20260310\n"
            "    -> laedt genau dieses Datum hoch\n",
            flush=True,
        )
        sys.exit(0 if len(sys.argv) == 2 else 1)

    date_str = None

    if len(sys.argv) == 2:
        date_str = _parse_date_arg(sys.argv[1])
        _log(f"Manueller Upload fuer Datum {date_str}")
    else:
        _log("Kein Datum uebergeben -> automatische Datumslogik")

    _show_paths(date_str)

    try:
        _log("Starte upload_nightly_batch() ...")
        success = upload_nightly_batch(date_str)
    except Exception as e:
        _log(f"Fehler im nightly upload: {e}")
        sys.exit(1)

    if success:
        _log("Nightly Upload erfolgreich")
        sys.exit(0)

    _log("Nightly Upload fehlgeschlagen")
    sys.exit(1)


if __name__ == "__main__":
    main()