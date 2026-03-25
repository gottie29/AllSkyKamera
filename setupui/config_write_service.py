#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import shutil
import subprocess
from datetime import datetime
from typing import Dict, Any, List


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "askutils", "config.py")
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "data", "config_backups")

UPLOAD_CMD = ["/usr/bin/python3", "-m", "scripts.upload_config_json", "--no-wait"]

EDITABLE_FIELDS = {
    "KAMERA_NAME": "string",
    "STANDORT_NAME": "string",
    "BENUTZER_NAME": "string",
    "KONTAKT_EMAIL": "string",
    "WEBSEITE": "string",
    "LATITUDE": "float",
    "LONGITUDE": "float",
    "ALLSKY_PATH": "string",
    "IMAGE_BASE_PATH": "string",
    "IMAGE_PATH": "string",
    "CAMERAID": "string",
}

PROTECTED_FIELDS = {
    "KAMERA_ID",
    "IMAGE_UPLOAD_SCRIPT",
    "NIGHTLY_UPLOAD_SCRIPT",
    "INDI",
}


def ensure_backup_dir() -> None:
    os.makedirs(BACKUP_DIR, exist_ok=True)


def create_backup() -> str:
    ensure_backup_dir()
    if not os.path.isfile(CONFIG_PATH):
        raise FileNotFoundError(f"config.py not found: {CONFIG_PATH}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"config_{ts}.py")
    shutil.copy2(CONFIG_PATH, backup_path)
    return backup_path

def list_backups() -> List[Dict[str, Any]]:
    ensure_backup_dir()
    items = []

    for name in sorted(os.listdir(BACKUP_DIR), reverse=True):
        path = os.path.join(BACKUP_DIR, name)
        if not os.path.isfile(path):
            continue
        stat = os.stat(path)
        items.append({
            "name": name,
            "path": path,
            "size": stat.st_size,
            "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        })

    return items


def _py_string(value: str) -> str:
    value = "" if value is None else str(value)
    return repr(value)


def _py_float(value: Any) -> str:
    try:
        return str(float(str(value).strip().replace(",", ".")))
    except Exception:
        raise ValueError(f"Invalid float value: {value}")


def _format_assignment(key: str, value: Any, value_type: str) -> str:
    if value_type == "string":
        rendered = _py_string(value)
    elif value_type == "float":
        rendered = _py_float(value)
    else:
        raise ValueError(f"Unsupported type: {value_type}")

    return f"{key} = {rendered}"


def save_config_values(new_values: Dict[str, Any]) -> Dict[str, Any]:
    if not os.path.isfile(CONFIG_PATH):
        raise FileNotFoundError(f"config.py not found: {CONFIG_PATH}")

    for key in new_values:
        if key in PROTECTED_FIELDS:
            raise ValueError(f"Field is protected and cannot be changed: {key}")
        if key not in EDITABLE_FIELDS:
            raise ValueError(f"Unknown or non-editable field: {key}")

    backup_path = create_backup()

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    original_content = content

    for key, raw_value in new_values.items():
        value_type = EDITABLE_FIELDS[key]
        replacement = _format_assignment(key, raw_value, value_type)

        pattern = rf"(?m)^\s*{re.escape(key)}\s*=\s*.*$"
        new_content, count = re.subn(pattern, replacement, content)

        if count == 0:
            raise ValueError(f"Field not found in config.py: {key}")

        content = new_content

    if content != original_content:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(content)

    return {
        "backup_path": backup_path,
        "changed": content != original_content,
    }


def restore_backup(filename: str) -> Dict[str, Any]:
    ensure_backup_dir()

    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise ValueError("Invalid backup filename")

    backup_path = os.path.join(BACKUP_DIR, filename)
    if not os.path.isfile(backup_path):
        raise FileNotFoundError(f"Backup not found: {filename}")

    current_backup = create_backup()
    shutil.copy2(backup_path, CONFIG_PATH)

    return {
        "restored_from": backup_path,
        "pre_restore_backup": current_backup,
    }


def run_config_upload() -> Dict[str, Any]:
    try:
        proc = subprocess.run(
            UPLOAD_CMD,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "command": "cd {} && {}".format(PROJECT_ROOT, " ".join(UPLOAD_CMD)),
        }
    except Exception as e:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "command": "cd {} && {}".format(PROJECT_ROOT, " ".join(UPLOAD_CMD)),
        }
        
def test_paths(allsky_path: str, image_base_path: str, image_path: str) -> Dict[str, Any]:
    result = {
        "allsky_path": {"ok": False, "msg": ""},
        "image_base_path": {"ok": False, "msg": ""},
        "image_path": {"ok": False, "msg": ""},
    }

    # -------------------------
    # 1. ALLSKY_PATH
    # -------------------------
    if os.path.isdir(allsky_path):
        result["allsky_path"] = {
            "ok": True,
            "msg": "Directory exists"
        }
    else:
        result["allsky_path"] = {
            "ok": False,
            "msg": "Directory not found"
        }

    # -------------------------
    # 2. IMAGE_BASE_PATH
    # -------------------------
    base_full = os.path.join(allsky_path, image_base_path)

    if os.path.isdir(base_full):
        try:
            entries = os.listdir(base_full)
            subdirs = [e for e in entries if os.path.isdir(os.path.join(base_full, e))]

            if subdirs:
                result["image_base_path"] = {
                    "ok": True,
                    "msg": f"{len(subdirs)} subdirectories found"
                }
            else:
                result["image_base_path"] = {
                    "ok": False,
                    "msg": "No subdirectories found"
                }
        except Exception as e:
            result["image_base_path"] = {
                "ok": False,
                "msg": str(e)
            }
    else:
        result["image_base_path"] = {
            "ok": False,
            "msg": "Directory not found"
        }

    # -------------------------
    # 3. IMAGE_PATH
    # -------------------------
    image_full = os.path.join(allsky_path, image_path)

    if os.path.isdir(image_full):
        try:
            files = os.listdir(image_full)
            found = any(f.lower() in ["image.jpg", "image.png"] for f in files)

            if found:
                result["image_path"] = {
                    "ok": True,
                    "msg": "image.jpg/png found"
                }
            else:
                result["image_path"] = {
                    "ok": False,
                    "msg": "No image.jpg or image.png found"
                }
        except Exception as e:
            result["image_path"] = {
                "ok": False,
                "msg": str(e)
            }
    else:
        result["image_path"] = {
            "ok": False,
            "msg": "Directory not found"
        }

    return result        