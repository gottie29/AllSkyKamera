#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta
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
            "mtime_ts": stat.st_mtime,
        })

    return items

def prune_backups_keep_latest(keep_latest: int = 3) -> Dict[str, Any]:
    ensure_backup_dir()

    backups = list_backups()
    keep_latest = max(0, int(keep_latest))

    to_keep = backups[:keep_latest]
    to_delete = backups[keep_latest:]

    deleted = []
    errors = []

    for item in to_delete:
        try:
            os.remove(item["path"])
            deleted.append(item["name"])
        except Exception as e:
            errors.append(f"{item['name']}: {e}")

    return {
        "kept": [b["name"] for b in to_keep],
        "deleted": deleted,
        "deleted_count": len(deleted),
        "error_count": len(errors),
        "errors": errors,
    }


def prune_old_backups(max_age_days: int = 90, keep_latest: int = 3) -> Dict[str, Any]:
    ensure_backup_dir()

    backups = list_backups()
    keep_latest = max(0, int(keep_latest))
    cutoff = datetime.now() - timedelta(days=int(max_age_days))

    deleted = []
    errors = []

    # Die neuesten X Backups immer behalten
    protected = backups[:keep_latest]
    candidates = backups[keep_latest:]

    for item in candidates:
        try:
            file_time = datetime.fromtimestamp(item["mtime_ts"])
            if file_time < cutoff:
                os.remove(item["path"])
                deleted.append(item["name"])
        except Exception as e:
            errors.append(f"{item['name']}: {e}")

    return {
        "kept": [b["name"] for b in protected],
        "deleted": deleted,
        "deleted_count": len(deleted),
        "error_count": len(errors),
        "errors": errors,
        "max_age_days": max_age_days,
    }

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

def _normalize_join(base: str, path_part: str) -> str:
    base = (base or "").strip()
    path_part = (path_part or "").strip()

    if not path_part:
        return os.path.abspath(os.path.expanduser(base))

    if os.path.isabs(path_part):
        return os.path.abspath(os.path.expanduser(path_part))

    return os.path.abspath(os.path.join(base, path_part))


def build_indi_live_candidates(allsky_path: str, image_base_path: str, image_path: str) -> List[str]:
    """
    Baut die Livebild-Kandidaten exakt nach der Logik aus image_upload_indi_api.py:
    1) IMAGE_BASE_PATH
    2) IMAGE_PATH
    3) Fallbacks unter ALLSKY_PATH und ALLSKY_PATH/images
    """
    candidates = []

    allsky_path = (allsky_path or "").strip()
    image_base_path = (image_base_path or "").strip()
    image_path = (image_path or "").strip()

    def add_pair(base_dir: str, name_no_ext: str) -> None:
        if not base_dir:
            return
        candidates.append(os.path.join(base_dir, name_no_ext + ".jpg"))
        candidates.append(os.path.join(base_dir, name_no_ext + ".png"))

    # 1) IMAGE_BASE_PATH
    if image_base_path:
        base_dir = _normalize_join(allsky_path, image_base_path)
        add_pair(base_dir, "latest")
        add_pair(base_dir, "image")

    # 2) IMAGE_PATH
    if image_path:
        base_dir = _normalize_join(allsky_path, image_path)
        add_pair(base_dir, "latest")
        add_pair(base_dir, "image")

    # 3) Fallbacks unter ALLSKY_PATH
    if allsky_path:
        base_dir = os.path.abspath(os.path.expanduser(allsky_path))
        add_pair(base_dir, "latest")
        add_pair(base_dir, "image")
        add_pair(os.path.join(base_dir, "images"), "latest")
        add_pair(os.path.join(base_dir, "images"), "image")

    # Duplikate entfernen, Reihenfolge behalten
    seen = set()
    unique = []
    for p in candidates:
        if p not in seen:
            unique.append(p)
            seen.add(p)

    return unique


def build_indi_primary_base(allsky_path: str, image_base_path: str) -> str:
    """
    Baut die INDI primary_base exakt nach nightly_upload_indi_api.py:
    - IMAGE_BASE_PATH absolut -> direkt
    - IMAGE_BASE_PATH relativ -> ALLSKY_PATH/IMAGE_BASE_PATH
    - IMAGE_BASE_PATH leer -> ALLSKY_PATH
    """
    allsky_path = (allsky_path or "").strip()
    image_base_path = (image_base_path or "").strip()

    if image_base_path:
        return _normalize_join(allsky_path, image_base_path)

    return os.path.abspath(os.path.expanduser(allsky_path))


def build_indi_nightly_date_dir(allsky_path: str, image_base_path: str, cameraid: str, date_str: str) -> str:
    """
    Baut den INDI-Tagesordner exakt nach nightly_upload_indi_api.py:
    primary_base/CAMERAID/timelapse/YYYYMMDD
    """
    primary_base = build_indi_primary_base(allsky_path, image_base_path)
    cameraid = (cameraid or "").strip()
    date_str = (date_str or "").strip()

    return os.path.join(primary_base, cameraid, "timelapse", date_str)

        
def test_paths(
    allsky_path: str,
    image_base_path: str,
    image_path: str,
    indi: bool = False,
    cameraid: str = "",
) -> Dict[str, Any]:
    result = {
        "allsky_path": {"ok": False, "msg": ""},
        "image_base_path": {"ok": False, "msg": ""},
        "image_path": {"ok": False, "msg": ""},
    }

    allsky_path = (allsky_path or "").strip()
    image_base_path = (image_base_path or "").strip()
    image_path = (image_path or "").strip()
    cameraid = (cameraid or "").strip()

    # --------------------------------
    # TJ / klassischer AllSky-Modus
    # --------------------------------
    if not indi:
        # 1) ALLSKY_PATH
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

        # 2) IMAGE_BASE_PATH
        base_full = os.path.join(allsky_path, image_base_path)

        if os.path.isdir(base_full):
            try:
                entries = os.listdir(base_full)
                subdirs = [e for e in entries if os.path.isdir(os.path.join(base_full, e))]

                if subdirs:
                    result["image_base_path"] = {
                        "ok": True,
                        "msg": "%d subdirectories found" % len(subdirs)
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

        # 3) IMAGE_PATH
        image_full = os.path.join(allsky_path, image_path)

        if os.path.isdir(image_full):
            try:
                files = {f.lower() for f in os.listdir(image_full)}

                found = any(f in files for f in ["image.jpg", "image.png"])
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

    # --------------------------------
    # INDI-Modus
    # --------------------------------

    # 1) ALLSKY_PATH
    allsky_exists = os.path.isdir(allsky_path)
    result["allsky_path"] = {
        "ok": allsky_exists,
        "msg": "Directory exists" if allsky_exists else "Directory not found"
    }

    # 2) IMAGE_BASE_PATH -> primary_base und Nightly-DateDir prüfen
    try:
        primary_base = build_indi_primary_base(allsky_path, image_base_path)
    except Exception as e:
        result["image_base_path"] = {
            "ok": False,
            "msg": "Primary base invalid: %s" % e
        }
        primary_base = ""

    if primary_base:
        primary_exists = os.path.isdir(primary_base)

        nightly_msg_parts = []
        nightly_ok = False

        if not primary_exists:
            nightly_msg_parts.append("primary_base not found: %s" % primary_base)
        else:
            nightly_msg_parts.append("primary_base exists: %s" % primary_base)

            if not cameraid:
                nightly_msg_parts.append("CAMERAID missing")
            else:
                if not cameraid:
                    nightly_msg_parts.append("CAMERAID missing")
                else:
                    timelapse_root = os.path.join(primary_base, cameraid, "timelapse")

                    if not os.path.isdir(timelapse_root):
                        nightly_msg_parts.append(f"timelapse dir not found: {timelapse_root}")
                    else:
                        try:
                            entries = os.listdir(timelapse_root)

                            # Nur echte Datumsordner YYYYMMDD erkennen
                            date_dirs = [
                                e for e in entries
                                if os.path.isdir(os.path.join(timelapse_root, e)) and e.isdigit() and len(e) == 8
                            ]

                            if date_dirs:
                                nightly_ok = True
                                # Optional: nur ein paar anzeigen
                                preview = date_dirs[:3]
                                more = ""
                                if len(date_dirs) > 3:
                                    more = f" (+{len(date_dirs)-3} more)"

                                nightly_msg_parts.append(
                                    f"{len(date_dirs)} date dirs found: {' | '.join(preview)}{more}"
                                )
                            else:
                                nightly_msg_parts.append("no date directories found in timelapse")

                        except Exception as e:
                            nightly_msg_parts.append(f"error reading timelapse dir: {e}")
                

        result["image_base_path"] = {
            "ok": primary_exists and nightly_ok,
            "msg": "; ".join(nightly_msg_parts)
        }

    # 3) IMAGE_PATH -> Livebild-Kandidaten nach echter INDI-Logik prüfen
    try:
        candidates = build_indi_live_candidates(allsky_path, image_base_path, image_path)
        found_files = [p for p in candidates if os.path.isfile(p)]

        if found_files:
            newest = max(found_files, key=os.path.getmtime)
            result["image_path"] = {
                "ok": True,
                "msg": "Live image found: %s" % newest
            }
        else:
            preview = candidates[:6]
            more = ""
            if len(candidates) > 6:
                more = " ... (+%d more)" % (len(candidates) - 6)

            result["image_path"] = {
                "ok": False,
                "msg": "No INDI live image found. Checked: %s%s" % (" | ".join(preview), more)
            }
    except Exception as e:
        result["image_path"] = {
            "ok": False,
            "msg": str(e)
        }

    return result