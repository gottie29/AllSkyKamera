# scripts/upload_config_json.py
# -*- coding: utf-8 -*-

import sys
from askutils.uploader import config_upload
from askutils.utils.logger import log


def main() -> int:
    # default: jitter an
    use_jitter = True

    # CLI Flag: --no-jitter
    if "--no-jitter" in sys.argv:
        use_jitter = False
        log("config_upload running with NO jitter")

    json_path = config_upload.create_config_json()
    if not json_path:
        return 1

    ok = config_upload.upload_to_ftp(json_path, use_jitter=use_jitter)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
