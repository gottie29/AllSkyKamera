#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
upload_config_json.py

Creates config.json from askutils/config.py and uploads it to the
AllSkyKamera server via FTP.

Options
-------
--no-jitter
    Disable the initial upload jitter delay.

--dry-run
    Create config.json but do NOT upload it.

--file <name>
    Custom output filename instead of default "config.json".

Exit codes
----------
0  success
1  JSON creation failed
2  FTP upload failed
"""

import sys
import argparse
from askutils.uploader import config_upload
from askutils.utils.logger import log


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create and upload config.json for AllSkyKamera"
    )

    parser.add_argument(
        "--no-jitter",
        action="store_true",
        help="Disable upload jitter"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Create JSON but do not upload it"
    )

    parser.add_argument(
        "--file",
        default="config.json",
        help="Output JSON filename (default: config.json)"
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    use_jitter = not args.no_jitter

    if args.no_jitter:
        log("config_upload running with NO jitter")

    json_path = config_upload.create_config_json(args.file)

    if not json_path:
        return 1

    if args.dry_run:
        log("config_upload dry-run enabled, skipping FTP upload")
        return 0

    ok = config_upload.upload_to_ftp(json_path, use_jitter=use_jitter)

    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())