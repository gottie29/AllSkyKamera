# scripts/run_indi_settings_upload.py
# -*- coding: utf-8 -*-

from askutils.uploader import indi_settings_upload
from askutils.utils.logger import log


def main() -> int:
    json_path = indi_settings_upload.create_indi_settings_json()
    if not json_path:
        return 0  # kein File gefunden / Dump fehlgeschlagen -> still

    ok = indi_settings_upload.upload_to_ftp(json_path)
    log(f"indi_settings_upload done ok={1 if ok else 0}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
