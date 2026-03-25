#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import sys
from typing import Optional, Dict, Any
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
UI_CONFIG_PATH = os.path.join(DATA_DIR, "ui_config.json")
SECRET_PATH = os.path.join(PROJECT_ROOT, "askutils", "ASKsecret.py")
SESSION_SECRET_PATH = os.path.join(DATA_DIR, "session_secret.txt")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def get_or_create_session_secret() -> str:
    ensure_data_dir()

    if os.path.isfile(SESSION_SECRET_PATH):
        try:
            with open(SESSION_SECRET_PATH, "r", encoding="utf-8") as f:
                value = f.read().strip()
            if value:
                return value
        except Exception:
            pass

    value = secrets.token_hex(32)

    tmp_path = SESSION_SECRET_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(value)
    os.replace(tmp_path, SESSION_SECRET_PATH)

    try:
        os.chmod(SESSION_SECRET_PATH, 0o600)
    except Exception:
        pass

    return value

def ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def ui_is_initialized() -> bool:
    data = load_ui_config()
    return bool(data.get("initialized"))


def load_ui_config() -> Dict[str, Any]:
    ensure_data_dir()
    if not os.path.isfile(UI_CONFIG_PATH):
        return {
            "initialized": False,
            "language": "de",
            "auth": {
                "username": "",
                "password_hash": ""
            },
            "cron_settings": {
                "image_upload_interval_min": 2,
                "nightly_upload_hour": 8,
                "nightly_upload_minute": 45,
                "settings_upload_interval_min": 10
            }
        }
    try:
        with open(UI_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("ui_config.json ist kein Objekt")
        return data
    except Exception:
        return {
            "initialized": False,
            "language": "de",
            "auth": {
                "username": "",
                "password_hash": ""
            }
        }


def save_ui_config(data: Dict[str, Any]) -> None:
    ensure_data_dir()
    tmp_path = UI_CONFIG_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, UI_CONFIG_PATH)
    try:
        os.chmod(UI_CONFIG_PATH, 0o600)
    except Exception:
        pass


def create_initial_user(username: str, password: str, language: str) -> None:
    language = language if language in ("de", "en") else "de"
    data = {
        "initialized": True,
        "language": language,
        "auth": {
            "username": username.strip(),
            "password_hash": generate_password_hash(password)
        }
    }
    save_ui_config(data)


def verify_login(username: str, password: str) -> bool:
    data = load_ui_config()
    auth = data.get("auth", {})
    stored_user = str(auth.get("username", "")).strip()
    password_hash = str(auth.get("password_hash", ""))

    if not stored_user or not password_hash:
        return False

    if username.strip() != stored_user:
        return False

    return check_password_hash(password_hash, password)


def update_credentials(username: str, password: str) -> None:
    data = load_ui_config()
    data["initialized"] = True
    data.setdefault("auth", {})
    data["auth"]["username"] = username.strip()
    data["auth"]["password_hash"] = generate_password_hash(password)
    save_ui_config(data)


def update_language(language: str) -> None:
    if language not in ("de", "en"):
        return
    data = load_ui_config()
    data["language"] = language
    save_ui_config(data)


def get_language() -> str:
    data = load_ui_config()
    lang = str(data.get("language", "de")).strip().lower()
    return lang if lang in ("de", "en") else "de"


def get_username() -> str:
    data = load_ui_config()
    return str(data.get("auth", {}).get("username", "")).strip()


def load_api_key_from_secret() -> Optional[str]:
    if not os.path.isfile(SECRET_PATH):
        return None

    namespace: Dict[str, Any] = {
        "__builtins__": __builtins__,
    }

    try:
        import base64
        namespace["base64"] = base64
        with open(SECRET_PATH, "r", encoding="utf-8") as f:
            code = f.read()
        exec(code, namespace, namespace)
        api_key = namespace.get("API_KEY")
        if api_key is None:
            return None
        return str(api_key)
    except Exception:
        return None


def verify_recovery_key(candidate: str) -> bool:
    real_key = load_api_key_from_secret()
    if not real_key:
        return False
    return candidate == real_key

def get_cron_settings() -> Dict[str, Any]:
    data = load_ui_config()
    cron = data.get("cron_settings", {}) or {}

    return {
        "image_upload_interval_min": int(cron.get("image_upload_interval_min", 2)),
        "nightly_upload_hour": int(cron.get("nightly_upload_hour", 8)),
        "nightly_upload_minute": int(cron.get("nightly_upload_minute", 45)),
        "settings_upload_interval_min": int(cron.get("settings_upload_interval_min", 10)),
    }


def update_cron_settings(image_upload_interval_min: int, nightly_upload_hour: int, nightly_upload_minute: int, settings_upload_interval_min: int) -> None:
    data = load_ui_config()
    data.setdefault("cron_settings", {})
    data["cron_settings"]["image_upload_interval_min"] = image_upload_interval_min
    data["cron_settings"]["nightly_upload_hour"] = nightly_upload_hour
    data["cron_settings"]["nightly_upload_minute"] = nightly_upload_minute
    data["cron_settings"]["settings_upload_interval_min"] = settings_upload_interval_min
    save_ui_config(data)