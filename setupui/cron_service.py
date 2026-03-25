#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
from typing import List, Dict, Any
from auth_service import get_cron_settings

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PYTHON_BIN = "/usr/bin/python3"

BLOCK_BEGIN = "# BEGIN ALLSKY BASE AUTOCRON"
BLOCK_END = "# END ALLSKY BASE AUTOCRON"

LEGACY_BASE_COMMENTS = {
    "Allsky Raspi-Status",
    "Allsky Image-Upload API",
    "Config Update",
    "Nightly API-Upload",
    "TJ Settings Upload",
    "INDI Settings Upload",
}

SENSOR_BLOCK_BEGIN = "# BEGIN ALLSKY SENSOR AUTOCRON"
SENSOR_BLOCK_END = "# END ALLSKY SENSOR AUTOCRON"

LEGACY_SENSOR_COMMENTS = {
    "BME280 Sensor",
    "DS18B20 Sensor",
    "TSL2591 Sensor",
    "MLX90614 Sensor",
    "DHT11 Sensor",
    "DHT22 Sensor",
    "HTU21 / GY-21 Sensor",
    "SHT3x Sensor",
}

OPTIONS_BLOCK_BEGIN = "# BEGIN ALLSKY OPTIONS AUTOCRON"
OPTIONS_BLOCK_END = "# END ALLSKY OPTIONS AUTOCRON"

LEGACY_OPTIONS_COMMENTS = {
    "KpIndex Logger",
    "Meteor Detection",
}

def _build_base_jobs(config_data: Dict[str, Any]) -> List[Dict[str, str]]:
    indi = bool(config_data.get("system", {}).get("indi", False))
    cron_settings = get_cron_settings()

    image_upload_interval = int(cron_settings.get("image_upload_interval_min", 2))
    nightly_hour = int(cron_settings.get("nightly_upload_hour", 8))
    nightly_minute = int(cron_settings.get("nightly_upload_minute", 45))
    settings_upload_interval = int(cron_settings.get("settings_upload_interval_min", 10))

    image_upload_module = "scripts.run_image_upload_indi_api" if indi else "scripts.run_image_upload_tj_api"
    nightly_upload_module = "scripts.run_nightly_upload_indi_api" if indi else "scripts.run_nightly_upload_tj_api"
    settings_upload_module = "scripts.run_indi_settings_upload" if indi else "scripts.run_tj_settings_upload"
    settings_upload_comment = "INDI Settings Upload" if indi else "TJ Settings Upload"

    jobs = [
        {
            "comment": "Allsky Raspi-Status",
            "schedule": "*/1 * * * *",
            "module": "scripts.raspi_status",
            "editable": False,
        },
        {
            "comment": "Allsky Image-Upload API",
            "schedule": f"*/{image_upload_interval} * * * *",
            "module": image_upload_module,
            "editable": True,
        },
        {
            "comment": "Config Update",
            "schedule": "0 12 * * *",
            "module": "scripts.upload_config_json",
            "editable": False,
        },
        {
            "comment": "Nightly API-Upload",
            "schedule": f"{nightly_minute} {nightly_hour} * * *",
            "module": nightly_upload_module,
            "editable": True,
        },
        {
            "comment": settings_upload_comment,
            "schedule": f"*/{settings_upload_interval} * * * *",
            "module": settings_upload_module,
            "editable": True,
        },
    ]

    for job in jobs:
        job["command"] = f"cd {PROJECT_ROOT} && {PYTHON_BIN} -m {job['module']}"

    return jobs



def render_base_block(config_data: Dict[str, Any]) -> str:
    jobs = _build_base_jobs(config_data)
    lines = [BLOCK_BEGIN]

    for job in jobs:
        lines.append(f"# AUTOCRON: {job['comment']}")
        lines.append(f"{job['schedule']} {job['command']}")

    lines.append(BLOCK_END)
    return "\n".join(lines) + "\n"


def get_desired_base_jobs(config_data: Dict[str, Any]) -> List[Dict[str, str]]:
    return _build_base_jobs(config_data)


def read_current_crontab() -> Dict[str, Any]:
    try:
        proc = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip().lower()
            if "no crontab for" in stderr:
                return {
                    "ok": True,
                    "raw": "",
                    "has_crontab": False,
                }
            return {
                "ok": False,
                "raw": "",
                "error": proc.stderr.strip() or "crontab -l failed",
            }

        return {
            "ok": True,
            "raw": proc.stdout,
            "has_crontab": True,
        }

    except Exception as e:
        return {
            "ok": False,
            "raw": "",
            "error": str(e),
        }


def extract_base_block(raw_crontab: str) -> str:
    if not raw_crontab:
        return ""

    lines = raw_crontab.splitlines()
    inside = False
    out = []

    for line in lines:
        if line.strip() == BLOCK_BEGIN:
            inside = True
            out.append(line)
            continue

        if inside:
            out.append(line)
            if line.strip() == BLOCK_END:
                break

    return "\n".join(out).strip()


def remove_base_block(raw_crontab: str) -> str:
    if not raw_crontab.strip():
        return ""

    lines = raw_crontab.splitlines()
    out = []
    inside = False

    for line in lines:
        stripped = line.strip()

        if stripped == BLOCK_BEGIN:
            inside = True
            continue

        if inside and stripped == BLOCK_END:
            inside = False
            continue

        if not inside:
            out.append(line)

    cleaned = "\n".join(out).strip()
    return cleaned + ("\n" if cleaned else "")

def remove_legacy_base_autocron_lines(raw_crontab: str) -> str:
    """
    Entfernt alte Basis-AUTOCRON-Einträge außerhalb des neuen Block-Formats.
    Sensor- und andere AUTOCRON-Einträge bleiben erhalten.
    """
    if not raw_crontab.strip():
        return ""

    lines = raw_crontab.splitlines()
    out = []
    skip_next = False

    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue

        stripped = line.strip()

        if stripped.startswith("# AUTOCRON:"):
            comment = stripped.replace("# AUTOCRON:", "", 1).strip()

            if comment in LEGACY_BASE_COMMENTS:
                # Kommentarzeile entfernen
                # und direkt folgende Cronzeile ebenfalls
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not next_line.startswith("#"):
                        skip_next = True
                continue

        out.append(line)

    cleaned = "\n".join(out).strip()
    return cleaned + ("\n" if cleaned else "")


def compare_base_block(config_data: Dict[str, Any], raw_crontab: str) -> Dict[str, Any]:
    desired = render_base_block(config_data).strip()
    current = extract_base_block(raw_crontab).strip()

    return {
        "desired_block": desired,
        "current_block": current,
        "in_sync": desired == current,
        "has_current_block": bool(current),
    }


def apply_base_crontab(config_data: Dict[str, Any]) -> Dict[str, Any]:
    current = read_current_crontab()
    if not current.get("ok"):
        return {
            "ok": False,
            "error": current.get("error", "Could not read crontab"),
        }

    raw = current.get("raw", "")
    without_block = remove_base_block(raw)
    without_legacy = remove_legacy_base_autocron_lines(without_block)
    desired_block = render_base_block(config_data)

    if without_legacy.strip():
        new_crontab = without_legacy.rstrip() + "\n\n" + desired_block
    else:
        new_crontab = desired_block
        
    try:
        proc = subprocess.run(
            ["crontab", "-"],
            input=new_crontab,
            capture_output=True,
            text=True,
            timeout=15,
        )

        if proc.returncode != 0:
            return {
                "ok": False,
                "error": proc.stderr.strip() or "crontab write failed",
            }

        return {
            "ok": True,
            "written_block": desired_block.strip(),
        }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }


def parse_base_jobs_from_block(block: str) -> List[Dict[str, str]]:
    if not block.strip():
        return []

    lines = [line.rstrip("\n") for line in block.splitlines()]
    jobs = []
    pending_comment = ""

    for line in lines:
        stripped = line.strip()

        if stripped in (BLOCK_BEGIN, BLOCK_END):
            continue

        if stripped.startswith("# AUTOCRON:"):
            pending_comment = stripped.replace("# AUTOCRON:", "", 1).strip()
            continue

        if stripped and not stripped.startswith("#"):
            parts = stripped.split(None, 5)
            if len(parts) >= 6:
                schedule = " ".join(parts[:5])
                command = parts[5]
            else:
                schedule = stripped
                command = ""

            jobs.append({
                "comment": pending_comment,
                "schedule": schedule,
                "command": command,
            })
            pending_comment = ""

    return jobs
    
def validate_base_cron_settings(image_upload_interval_min: int, nightly_upload_hour: int, nightly_upload_minute: int, settings_upload_interval_min: int) -> Dict[str, str]:
    errors = {}

    if image_upload_interval_min not in (2, 3, 4, 5):
        errors["image_upload_interval_min"] = "Image upload interval must be between 2 and 5 minutes."

    if not (0 <= nightly_upload_hour <= 23):
        errors["nightly_upload_hour"] = "Nightly upload hour must be between 0 and 23."

    if not (0 <= nightly_upload_minute <= 59):
        errors["nightly_upload_minute"] = "Nightly upload minute must be between 0 and 59."

    allowed_settings_intervals = (10, 20, 30, 60, 120, 180, 240, 300, 360)
    if settings_upload_interval_min not in allowed_settings_intervals:
        errors["settings_upload_interval_min"] = "Settings upload interval must be between every 10 minutes and every 6 hours."

    return errors    

def build_sensor_jobs(config_data: Dict[str, Any]) -> List[Dict[str, str]]:
    sensors = config_data.get("sensors", {})
    jobs = []

    def add_job(enabled, comment, schedule, module):
        if enabled:
            jobs.append({
                "comment": comment,
                "schedule": schedule,
                "module": module,
                "command": f"cd {PROJECT_ROOT} && {PYTHON_BIN} -m {module}",
            })

    add_job(
        sensors.get("bme280_enabled"),
        "BME280 Sensor",
        "*/%s * * * *" % int(sensors.get("bme280_log_interval_min") or 1),
        "scripts.bme280_logger",
    )

    add_job(
        sensors.get("ds18b20_enabled"),
        "DS18B20 Sensor",
        "*/%s * * * *" % int(sensors.get("ds18b20_log_interval_min") or 1),
        "scripts.ds18b20_logger",
    )

    add_job(
        sensors.get("tsl2591_enabled"),
        "TSL2591 Sensor",
        "*/%s * * * *" % int(sensors.get("tsl2591_log_interval_min") or 1),
        "scripts.tsl2591_logger",
    )

    add_job(
        sensors.get("mlx90614_enabled"),
        "MLX90614 Sensor",
        "*/%s * * * *" % int(sensors.get("mlx90614_log_interval_min") or 1),
        "scripts.mlx90614_logger",
    )

    add_job(
        sensors.get("dht11_enabled"),
        "DHT11 Sensor",
        "*/%s * * * *" % int(sensors.get("dht11_log_interval_min") or 1),
        "scripts.dht11_logger",
    )

    add_job(
        sensors.get("dht22_enabled"),
        "DHT22 Sensor",
        "*/%s * * * *" % int(sensors.get("dht22_log_interval_min") or 1),
        "scripts.dht22_logger",
    )

    add_job(
        sensors.get("htu21_enabled"),
        "HTU21 / GY-21 Sensor",
        "*/%s * * * *" % int(sensors.get("htu21_log_interval_min") or 1),
        "scripts.htu21_logger",
    )

    add_job(
        sensors.get("sht3x_enabled"),
        "SHT3x Sensor",
        "*/%s * * * *" % int(sensors.get("sht3x_log_interval_min") or 1),
        "scripts.sht3x_logger",
    )

    return jobs


def render_sensor_block(config_data: Dict[str, Any]) -> str:
    jobs = build_sensor_jobs(config_data)
    lines = [SENSOR_BLOCK_BEGIN]

    for job in jobs:
        lines.append(f"# AUTOCRON: {job['comment']}")
        lines.append(f"{job['schedule']} {job['command']}")

    lines.append(SENSOR_BLOCK_END)
    return "\n".join(lines) + "\n"


def extract_sensor_block(raw_crontab: str) -> str:
    if not raw_crontab:
        return ""

    lines = raw_crontab.splitlines()
    inside = False
    out = []

    for line in lines:
        if line.strip() == SENSOR_BLOCK_BEGIN:
            inside = True
            out.append(line)
            continue

        if inside:
            out.append(line)
            if line.strip() == SENSOR_BLOCK_END:
                break

    return "\n".join(out).strip()


def remove_sensor_block(raw_crontab: str) -> str:
    if not raw_crontab.strip():
        return ""

    lines = raw_crontab.splitlines()
    out = []
    inside = False

    for line in lines:
        stripped = line.strip()

        if stripped == SENSOR_BLOCK_BEGIN:
            inside = True
            continue

        if inside and stripped == SENSOR_BLOCK_END:
            inside = False
            continue

        if not inside:
            out.append(line)

    cleaned = "\n".join(out).strip()
    return cleaned + ("\n" if cleaned else "")


def remove_legacy_sensor_autocron_lines(raw_crontab: str) -> str:
    if not raw_crontab.strip():
        return ""

    lines = raw_crontab.splitlines()
    out = []
    skip_next = False

    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue

        stripped = line.strip()

        if stripped.startswith("# AUTOCRON:"):
            comment = stripped.replace("# AUTOCRON:", "", 1).strip()

            if comment in LEGACY_SENSOR_COMMENTS:
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not next_line.startswith("#"):
                        skip_next = True
                continue

        out.append(line)

    cleaned = "\n".join(out).strip()
    return cleaned + ("\n" if cleaned else "")


def compare_sensor_block(config_data: Dict[str, Any], raw_crontab: str) -> Dict[str, Any]:
    desired = render_sensor_block(config_data).strip()
    current = extract_sensor_block(raw_crontab).strip()

    return {
        "desired_block": desired,
        "current_block": current,
        "in_sync": desired == current,
        "has_current_block": bool(current),
    }


def apply_sensor_crontab(config_data: Dict[str, Any]) -> Dict[str, Any]:
    current = read_current_crontab()
    if not current.get("ok"):
        return {
            "ok": False,
            "error": current.get("error", "Could not read crontab"),
        }

    raw = current.get("raw", "")
    without_sensor_block = remove_sensor_block(raw)
    without_legacy_sensor = remove_legacy_sensor_autocron_lines(without_sensor_block)
    desired_block = render_sensor_block(config_data)

    if without_legacy_sensor.strip():
        new_crontab = without_legacy_sensor.rstrip() + "\n\n" + desired_block
    else:
        new_crontab = desired_block

    try:
        proc = subprocess.run(
            ["crontab", "-"],
            input=new_crontab,
            capture_output=True,
            text=True,
            timeout=15,
        )

        if proc.returncode != 0:
            return {
                "ok": False,
                "error": proc.stderr.strip() or "crontab write failed",
            }

        return {
            "ok": True,
            "written_block": desired_block.strip(),
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }


def parse_sensor_jobs_from_block(block: str) -> List[Dict[str, str]]:
    if not block.strip():
        return []

    lines = [line.rstrip("\n") for line in block.splitlines()]
    jobs = []
    pending_comment = ""

    for line in lines:
        stripped = line.strip()

        if stripped in (SENSOR_BLOCK_BEGIN, SENSOR_BLOCK_END):
            continue

        if stripped.startswith("# AUTOCRON:"):
            pending_comment = stripped.replace("# AUTOCRON:", "", 1).strip()
            continue

        if stripped and not stripped.startswith("#"):
            parts = stripped.split(None, 5)
            if len(parts) >= 6:
                schedule = " ".join(parts[:5])
                command = parts[5]
            else:
                schedule = stripped
                command = ""

            jobs.append({
                "comment": pending_comment,
                "schedule": schedule,
                "command": command,
            })
            pending_comment = ""

    return jobs
    
def build_option_jobs(config_data: Dict[str, Any]) -> List[Dict[str, str]]:
    features = config_data.get("features", {})
    jobs = []

    def add_job(enabled, comment, schedule, module):
        if enabled:
            jobs.append({
                "comment": comment,
                "schedule": schedule,
                "module": module,
                "command": f"cd {PROJECT_ROOT} && {PYTHON_BIN} -m {module}",
            })

    add_job(
        features.get("kpindex_enabled"),
        "KpIndex Logger",
        "*/%s * * * *" % int(features.get("kpindex_log_interval_min") or 15),
        "scripts.kpindex_logger",
    )

    # Hier Modulnamen ggf. an dein echtes Skript anpassen
    add_job(
        features.get("meteor_enabled"),
        "Meteor Detection",
        "*/10 * * * *",
        "scripts.run_meteor_detection_api",
    )

    return jobs


def render_option_block(config_data: Dict[str, Any]) -> str:
    jobs = build_option_jobs(config_data)
    lines = [OPTIONS_BLOCK_BEGIN]

    for job in jobs:
        lines.append(f"# AUTOCRON: {job['comment']}")
        lines.append(f"{job['schedule']} {job['command']}")

    lines.append(OPTIONS_BLOCK_END)
    return "\n".join(lines) + "\n"


def extract_option_block(raw_crontab: str) -> str:
    if not raw_crontab:
        return ""

    lines = raw_crontab.splitlines()
    inside = False
    out = []

    for line in lines:
        if line.strip() == OPTIONS_BLOCK_BEGIN:
            inside = True
            out.append(line)
            continue

        if inside:
            out.append(line)
            if line.strip() == OPTIONS_BLOCK_END:
                break

    return "\n".join(out).strip()


def remove_option_block(raw_crontab: str) -> str:
    if not raw_crontab.strip():
        return ""

    lines = raw_crontab.splitlines()
    out = []
    inside = False

    for line in lines:
        stripped = line.strip()

        if stripped == OPTIONS_BLOCK_BEGIN:
            inside = True
            continue

        if inside and stripped == OPTIONS_BLOCK_END:
            inside = False
            continue

        if not inside:
            out.append(line)

    cleaned = "\n".join(out).strip()
    return cleaned + ("\n" if cleaned else "")


def remove_legacy_option_autocron_lines(raw_crontab: str) -> str:
    if not raw_crontab.strip():
        return ""

    lines = raw_crontab.splitlines()
    out = []
    skip_next = False

    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue

        stripped = line.strip()

        if stripped.startswith("# AUTOCRON:"):
            comment = stripped.replace("# AUTOCRON:", "", 1).strip()

            if comment in LEGACY_OPTIONS_COMMENTS:
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not next_line.startswith("#"):
                        skip_next = True
                continue

        out.append(line)

    cleaned = "\n".join(out).strip()
    return cleaned + ("\n" if cleaned else "")


def compare_option_block(config_data: Dict[str, Any], raw_crontab: str) -> Dict[str, Any]:
    desired = render_option_block(config_data).strip()
    current = extract_option_block(raw_crontab).strip()

    return {
        "desired_block": desired,
        "current_block": current,
        "in_sync": desired == current,
        "has_current_block": bool(current),
    }


def apply_option_crontab(config_data: Dict[str, Any]) -> Dict[str, Any]:
    current = read_current_crontab()
    if not current.get("ok"):
        return {
            "ok": False,
            "error": current.get("error", "Could not read crontab"),
        }

    raw = current.get("raw", "")
    without_option_block = remove_option_block(raw)
    without_legacy_option = remove_legacy_option_autocron_lines(without_option_block)
    desired_block = render_option_block(config_data)

    if without_legacy_option.strip():
        new_crontab = without_legacy_option.rstrip() + "\n\n" + desired_block
    else:
        new_crontab = desired_block

    try:
        proc = subprocess.run(
            ["crontab", "-"],
            input=new_crontab,
            capture_output=True,
            text=True,
            timeout=15,
        )

        if proc.returncode != 0:
            return {
                "ok": False,
                "error": proc.stderr.strip() or "crontab write failed",
            }

        return {
            "ok": True,
            "written_block": desired_block.strip(),
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }


def parse_option_jobs_from_block(block: str) -> List[Dict[str, str]]:
    if not block.strip():
        return []

    lines = [line.rstrip("\n") for line in block.splitlines()]
    jobs = []
    pending_comment = ""

    for line in lines:
        stripped = line.strip()

        if stripped in (OPTIONS_BLOCK_BEGIN, OPTIONS_BLOCK_END):
            continue

        if stripped.startswith("# AUTOCRON:"):
            pending_comment = stripped.replace("# AUTOCRON:", "", 1).strip()
            continue

        if stripped and not stripped.startswith("#"):
            parts = stripped.split(None, 5)
            if len(parts) >= 6:
                schedule = " ".join(parts[:5])
                command = parts[5]
            else:
                schedule = stripped
                command = ""

            jobs.append({
                "comment": pending_comment,
                "schedule": schedule,
                "command": command,
            })
            pending_comment = ""

    return jobs