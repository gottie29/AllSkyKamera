#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import shutil
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "askutils", "config.py")
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "data", "config_backups")


def ensure_backup_dir():
    if not os.path.isdir(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)


def create_backup():
    ensure_backup_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, "config_%s.py" % ts)
    shutil.copy2(CONFIG_PATH, backup_path)
    return backup_path


def _read_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _write_config(content):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def _replace_simple_assignment(content, key, rendered_value):
    pattern = r'(?m)^\s*' + re.escape(key) + r'\s*=\s*.*$'
    replacement = "%s = %s" % (key, rendered_value)
    new_content, count = re.subn(pattern, replacement, content)
    if count == 0:
        raise ValueError("Field not found in config.py: %s" % key)
    return new_content


def _py_bool(v):
    return "True" if bool(v) else "False"


def _py_string(v):
    return repr("" if v is None else str(v))


def _py_int(v):
    return str(int(str(v).strip()))


def _py_float(v):
    return str(float(str(v).strip().replace(",", ".")))


def save_kpindex_settings(payload):
    content = _read_config()
    backup_path = create_backup()

    content = _replace_simple_assignment(content, "KPINDEX_ENABLED", _py_bool(payload.get("enabled")))
    content = _replace_simple_assignment(content, "KPINDEX_OVERLAY", _py_bool(payload.get("overlay")))
    content = _replace_simple_assignment(content, "KPINDEX_LOG_INTERVAL_MIN", _py_int(payload.get("log_interval_min", 15)))

    _write_config(content)
    return {"ok": True, "backup_path": backup_path}


def save_meteor_settings(payload):
    content = _read_config()
    backup_path = create_backup()

    content = _replace_simple_assignment(content, "METEOR_ENABLE", _py_bool(payload.get("enabled")))
    content = _replace_simple_assignment(content, "METEOR_OUTPUT_DIR", _py_string(payload.get("output_dir", "")))
    content = _replace_simple_assignment(content, "METEOR_STATE_FILE", _py_string(payload.get("state_file", "")))
    content = _replace_simple_assignment(content, "METEOR_KEEP_DAYS_LOCAL", _py_int(payload.get("keep_days_local", 3)))
    content = _replace_simple_assignment(content, "METEOR_THRESHOLD", _py_int(payload.get("threshold", 80)))
    content = _replace_simple_assignment(content, "METEOR_MIN_PIXELS", _py_int(payload.get("min_pixels", 1200)))
    content = _replace_simple_assignment(content, "METEOR_MIN_BLOB_PIXELS", _py_int(payload.get("min_blob_pixels", 25)))
    content = _replace_simple_assignment(content, "METEOR_MIN_LINE_LENGTH", _py_int(payload.get("min_line_length", 20)))
    content = _replace_simple_assignment(content, "METEOR_MIN_ASPECT_RATIO", _py_float(payload.get("min_aspect_ratio", 4.0)))
    content = _replace_simple_assignment(content, "METEOR_FULLHD_WIDTH", _py_int(payload.get("fullhd_width", 1920)))
    content = _replace_simple_assignment(content, "METEOR_SMALL_WIDTH", _py_int(payload.get("small_width", 640)))
    content = _replace_simple_assignment(content, "METEOR_DIFF_WIDTH", _py_int(payload.get("diff_width", 640)))
    content = _replace_simple_assignment(content, "METEOR_BOXED_WIDTH", _py_int(payload.get("boxed_width", 640)))
    content = _replace_simple_assignment(content, "METEOR_PREV_SMALL_WIDTH", _py_int(payload.get("prev_small_width", 640)))
    content = _replace_simple_assignment(content, "METEOR_UPLOAD_JITTER_MAX_SECONDS", _py_int(payload.get("upload_jitter_max_seconds", 90)))

    _write_config(content)
    return {"ok": True, "backup_path": backup_path}