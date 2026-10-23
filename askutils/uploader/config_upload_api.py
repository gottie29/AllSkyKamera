#!/usr/bin/env python3
# askutils/uploader/config_upload_api.py

import json
import os
import random
import time
from urllib.parse import urlsplit
from askutils.ASKsecret import API_URL
from typing import Optional

import requests

from askutils import config
from askutils.utils.logger import log, error


try:
    from askutils.ASKsecret import API_KEY
except Exception:
    API_KEY = None

HTTP_CONNECT_TIMEOUT = 20
HTTP_READ_TIMEOUT = 120

TYPE_TO_FILENAME = {
    "config": "config.json",
    "tj_settings": "tj_settings.json",
    "indi_settings": "indi_settings.json",
}


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default

def _get_api_url() -> str:
    parts = urlsplit(API_URL)
    return f"{parts.scheme}://{parts.netloc}/api/v1/config_upload.php"

def _apply_initial_jitter(use_jitter: bool) -> None:
    if not use_jitter:
        log("config_upload_api jitter_disabled")
        return

    max_seconds = _safe_int(
        getattr(config, "CONFIG_UPLOAD_JITTER_MAX_SECONDS", 180), 180
    )
    if max_seconds <= 0:
        return

    delay = random.randint(0, max_seconds)
    if delay > 0:
        log(f"config_upload_api jitter_seconds={delay}")
        time.sleep(delay)


def _sleep_retry_window(min_seconds: int, max_seconds: int) -> None:
    delay = random.randint(min_seconds, max_seconds)
    log(f"config_upload_api retry_sleep_seconds={delay}")
    time.sleep(delay)


def _validate_json_file(filepath: str, upload_type: str) -> Optional[str]:
    expected_filename = TYPE_TO_FILENAME.get(upload_type)
    if expected_filename is None:
        error(f"config_upload_api invalid_type type={upload_type}")
        return None

    if not filepath or not os.path.isfile(filepath):
        error(f"config_upload_api file_not_found file={filepath}")
        return None

    if os.path.basename(filepath) != expected_filename:
        error(
            "config_upload_api invalid_filename "
            f"expected={expected_filename} actual={os.path.basename(filepath)}"
        )
        return None

    try:
        with open(filepath, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        error(f"config_upload_api invalid_json error={exc}")
        return None

    if not isinstance(payload, dict):
        error("config_upload_api invalid_json_structure")
        return None

    return expected_filename


def _upload_once(filepath: str, upload_type: str, filename: str) -> bool:
    if not API_KEY:
        error("config_upload_api API_KEY fehlt")
        return False

    try:
        with open(filepath, "rb") as handle:
            response = requests.post(
                _get_api_url(),
                headers={"X-API-Key": API_KEY},
                data={"type": upload_type},
                files={"file": (filename, handle, "application/json")},
                timeout=(HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT),
                verify=True,
            )
    except requests.RequestException as exc:
        error(f"config_upload_api request_failed error={exc}")
        return False
    except Exception as exc:
        error(f"config_upload_api prepare_failed error={exc}")
        return False

    try:
        payload = response.json()
    except Exception:
        error(f"config_upload_api invalid_response status={response.status_code}")
        return False

    if response.status_code == 200 and payload.get("ok") is True:
        if payload.get("type") != upload_type or payload.get("filename") != filename:
            error("config_upload_api response_mapping_mismatch")
            return False
        return True

    error(
        "config_upload_api upload_rejected "
        f"status={response.status_code} error={payload.get('error', 'unknown')}"
    )
    return False


def upload_config_api(
    filepath: str,
    upload_type: str,
    use_jitter: bool = True,
    use_retry_sleep: bool = True,
) -> bool:
    filename = _validate_json_file(filepath, upload_type)
    if filename is None:
        return False

    max_age = _safe_int(getattr(config, "CONFIG_UPLOAD_MAX_AGE_SECONDS", 0), 0)
    if max_age > 0:
        try:
            age = time.time() - os.path.getmtime(filepath)
            if age > max_age:
                error(
                    "config_upload_api file_too_old "
                    f"age_seconds={int(age)} max_age_seconds={max_age}"
                )
                return False
        except OSError:
            pass

    _apply_initial_jitter(use_jitter)

    max_retries = max(
        0,
        _safe_int(getattr(config, "CONFIG_UPLOAD_MAX_RETRIES", 3), 3),
    )
    retry_min = max(
        0,
        _safe_int(getattr(config, "CONFIG_UPLOAD_RETRY_MIN_SECONDS", 120), 120),
    )
    retry_max = max(
        retry_min,
        _safe_int(getattr(config, "CONFIG_UPLOAD_RETRY_MAX_SECONDS", 300), 300),
    )

    attempt = 0
    while True:
        attempt += 1
        if _upload_once(filepath, upload_type, filename):
            log(
                "config_upload_api upload_ok "
                f"attempt={attempt} type={upload_type} file={filename}"
            )
            return True

        if attempt > max_retries:
            error(
                "config_upload_api giving_up "
                f"attempts={attempt} max_retries={max_retries} type={upload_type}"
            )
            return False

        if use_retry_sleep:
            _sleep_retry_window(retry_min, retry_max)
        else:
            log("config_upload_api retry_sleep_disabled")

