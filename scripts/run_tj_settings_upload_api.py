#!/usr/bin/env python3

import argparse

from askutils.uploader import config_upload_api, tj_settings_upload
from askutils.utils.logger import log


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create and upload tj_settings.json through the AllSkyKamera API"
    )
    parser.add_argument("--no-jitter", action="store_true")
    parser.add_argument("--no-wait", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    json_path = tj_settings_upload.create_tj_settings_json()
    if not json_path:
        return 0

    ok = config_upload_api.upload_config_api(
        json_path,
        "tj_settings",
        use_jitter=not (args.no_jitter or args.no_wait),
        use_retry_sleep=not args.no_wait,
    )
    log(f"tj_settings_upload_api done ok={1 if ok else 0}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

