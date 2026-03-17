#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
from datetime import datetime
from typing import Optional

from askutils.uploader.nightly_upload_indi_api import upload_nightly_batch
from askutils import config


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("[{0}] {1}".format(ts, msg), flush=True)


def _parse_date_arg(arg: str) -> str:
    _log("Pruefe Datumsargument: {0}".format(arg))

    try:
        dt = datetime.strptime(arg, "%Y%m%d")
    except ValueError:
        _log("Fehler: Datum muss im Format JJJJMMTT angegeben werden, z.B. 20260310.")
        sys.exit(1)

    normalized = dt.strftime("%Y%m%d")
    _log("Datumsargument gueltig: {0}".format(normalized))
    return normalized


def _get_camera_id() -> str:
    return str(
        getattr(config, "CAMERAID", None)
        or getattr(config, "KAMERA_ID", None)
        or getattr(config, "KAMERA", None)
        or "UNKNOWN"
    )


def _get_image_root() -> str:
    allsky_path = getattr(config, "ALLSKY_PATH", "") or ""
    image_base_path = getattr(config, "IMAGE_BASE_PATH", "") or ""

    if image_base_path:
        if os.path.isabs(image_base_path):
            return os.path.abspath(image_base_path)
        return os.path.abspath(os.path.join(allsky_path, image_base_path))

    return os.path.abspath(allsky_path)


def _show_paths(date_str: Optional[str]) -> None:
    """
    Zeigt nur die aus config.py abgeleiteten Pfade an.
    """
    _log("---- Konfiguration / Pfade ----")

    try:
        kamera_id = _get_camera_id()
        allsky_path = getattr(config, "ALLSKY_PATH", "") or ""
        image_base_path = getattr(config, "IMAGE_BASE_PATH", "") or ""
        image_path = getattr(config, "IMAGE_PATH", "") or ""
        image_root = _get_image_root()

        _log("CAMERAID/KAMERA_ID: {0}".format(kamera_id))
        _log("ALLSKY_PATH: {0}".format(allsky_path))
        _log("IMAGE_BASE_PATH: {0}".format(image_base_path))
        _log("IMAGE_PATH: {0}".format(image_path))
        _log("IMAGE_ROOT: {0}".format(image_root))

    except Exception as e:
        _log("Fehler beim Lesen der Config: {0}".format(e))
        return

    if date_str:
        _log("Nightly Datum: {0}".format(date_str))
    else:
        _log("Nightly Datum: automatisch (gestern)")

    try:
        paths = [image_root]

        if date_str:
            indi_date_dir = os.path.join(image_root, kamera_id, "timelapse", date_str)
            paths.extend([
                indi_date_dir,
            ])

        _log("---- Abgeleitete Dateipfade ----")
        for p in paths:
            exists = "OK" if os.path.exists(p) else "MISSING"
            _log("{0}  {1}".format(exists, p))

    except Exception as e:
        _log("Pfade konnten nicht geprueft werden: {0}".format(e))

    _log("-----------------------------")


def main() -> None:
    _log("Starte run_nightly_upload_indi_api")

    if len(sys.argv) > 2 or (len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help")):
        print(
            "Verwendung:\n"
            "  python3 -m scripts.run_nightly_upload_indi_api\n"
            "    -> laedt die letzte Nacht (gestern) hoch\n\n"
            "  python3 -m scripts.run_nightly_upload_indi_api 20260310\n"
            "    -> laedt genau dieses Datum hoch\n",
            flush=True,
        )
        sys.exit(0 if len(sys.argv) == 2 else 1)

    date_str = None

    if len(sys.argv) == 2:
        date_str = _parse_date_arg(sys.argv[1])
        _log("Manueller Upload fuer Datum {0}".format(date_str))
    else:
        _log("Kein Datum uebergeben -> automatische Datumslogik")

    _show_paths(date_str)

    try:
        _log("Starte upload_nightly_batch() ...")
        success = upload_nightly_batch(date_str)
    except Exception as e:
        _log("Fehler im nightly upload: {0}".format(e))
        sys.exit(1)

    if success:
        _log("Nightly Upload erfolgreich")
        sys.exit(0)

    _log("Nightly Upload fehlgeschlagen")
    sys.exit(1)


if __name__ == "__main__":
    main()