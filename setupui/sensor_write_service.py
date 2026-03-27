#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import ast
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


def _py_float(v):
    text = str(v).strip().replace(",", ".")
    return str(float(text))


def _py_int(v):
    return str(int(str(v).strip()))


def _py_address(v):
    if v is None or str(v).strip() == "":
        return "0x00"
    text = str(v).strip().lower()
    if text.startswith("0x"):
        return hex(int(text, 16))
    return hex(int(text))


def _render_bme280_list(items):
    lines = ["["]
    for item in items:
        lines.append("    {")
        lines.append('        "enabled": %s,' % _py_bool(item.get("enabled")))
        lines.append('        "name": %s,' % _py_string(item.get("name", "")))
        lines.append('        "address": %s,' % _py_address(item.get("address")))
        lines.append('        "overlay": %s,' % _py_bool(item.get("overlay")))
        lines.append('        "temp_offset_c": %s,' % _py_float(item.get("temp_offset_c", 0.0)))
        lines.append('        "press_offset_hpa": %s,' % _py_float(item.get("press_offset_hpa", 0.0)))
        lines.append('        "hum_offset_pct": %s,' % _py_float(item.get("hum_offset_pct", 0.0)))
        lines.append("    },")
    lines.append("]")
    return "\n".join(lines)


def _render_dht22_list(items):
    lines = ["["]
    for item in items:
        lines.append("    {")
        lines.append('        "enabled": %s,' % _py_bool(item.get("enabled")))
        lines.append('        "name": %s,' % _py_string(item.get("name", "")))
        lines.append('        "gpio_bcm": %s,' % _py_int(item.get("gpio_bcm", 0)))
        lines.append('        "retries": %s,' % _py_int(item.get("retries", 5)))
        lines.append('        "retry_delay": %s,' % _py_float(item.get("retry_delay", 0.3)))
        lines.append('        "overlay": %s,' % _py_bool(item.get("overlay")))
        lines.append('        "temp_offset_c": %s,' % _py_float(item.get("temp_offset_c", 0.0)))
        lines.append('        "hum_offset_pct": %s,' % _py_float(item.get("hum_offset_pct", 0.0)))
        lines.append("    },")
    lines.append("]")
    return "\n".join(lines)


def _replace_list_assignment(content, key, rendered_list):
    pattern = r'(?ms)^\s*' + re.escape(key) + r'\s*=\s*\[.*?^\s*\]'
    replacement = "%s = %s" % (key, rendered_list)
    new_content, count = re.subn(pattern, replacement, content)
    if count == 0:
        raise ValueError("List field not found in config.py: %s" % key)
    return new_content


def _extract_list_literal(content, key):
    pattern = r'(?ms)^\s*' + re.escape(key) + r'\s*=\s*(\[(?:.|\n)*?^\s*\])'
    m = re.search(pattern, content)
    if not m:
        return None
    return m.group(1)


def save_bme280_settings(payload):
    content = _read_config()
    backup_path = create_backup()

    mode = payload.get("mode", "single")

    if mode == "multi":
        items = payload.get("items", [])
        rendered = _render_bme280_list(items)
        content = _replace_simple_assignment(content, "BME280_ENABLED", _py_bool(payload.get("enabled")))
        content = _replace_simple_assignment(content, "BME280_LOG_INTERVAL_MIN", _py_int(payload.get("log_interval_min", 1)))

        if _extract_list_literal(content, "BME280_SENSORS") is None:
            raise ValueError("BME280_SENSORS not found in config.py")
        content = _replace_list_assignment(content, "BME280_SENSORS", rendered)
    else:
        item = payload.get("items", [{}])[0]
        content = _replace_simple_assignment(content, "BME280_ENABLED", _py_bool(payload.get("enabled")))
        content = _replace_simple_assignment(content, "BME280_NAME", _py_string(item.get("name", "")))
        content = _replace_simple_assignment(content, "BME280_I2C_ADDRESS", _py_address(item.get("address")))
        content = _replace_simple_assignment(content, "BME280_OVERLAY", _py_bool(item.get("overlay")))
        content = _replace_simple_assignment(content, "BME280_TEMP_OFFSET_C", _py_float(item.get("temp_offset_c", 0.0)))
        content = _replace_simple_assignment(content, "BME280_PRESS_OFFSET_HPA", _py_float(item.get("press_offset_hpa", 0.0)))
        content = _replace_simple_assignment(content, "BME280_HUM_OFFSET_PCT", _py_float(item.get("hum_offset_pct", 0.0)))
        content = _replace_simple_assignment(content, "BME280_LOG_INTERVAL_MIN", _py_int(payload.get("log_interval_min", 1)))

    _write_config(content)
    return {"ok": True, "backup_path": backup_path}

def save_ds18b20_settings(payload):
    content = _read_config()
    backup_path = create_backup()

    item = payload.get("items", [{}])[0]

    content = _replace_simple_assignment(content, "DS18B20_ENABLED", _py_bool(payload.get("enabled")))
    content = _replace_simple_assignment(content, "DS18B20_NAME", _py_string(item.get("name", "")))
    content = _replace_simple_assignment(content, "DS18B20_OVERLAY", _py_bool(item.get("overlay")))
    content = _replace_simple_assignment(content, "DS18B20_TEMP_OFFSET_C", _py_float(item.get("temp_offset_c", 0.0)))
    content = _replace_simple_assignment(content, "DS18B20_LOG_INTERVAL_MIN", _py_int(payload.get("log_interval_min", 1)))

    _write_config(content)
    return {"ok": True, "backup_path": backup_path}

def save_dht11_settings(payload):
    content = _read_config()
    backup_path = create_backup()

    item = payload.get("items", [{}])[0]

    content = _replace_simple_assignment(content, "DHT11_ENABLED", _py_bool(payload.get("enabled")))
    content = _replace_simple_assignment(content, "DHT11_NAME", _py_string(item.get("name", "")))
    content = _replace_simple_assignment(content, "DHT11_GPIO_BCM", _py_int(item.get("gpio_bcm", 0)))
    content = _replace_simple_assignment(content, "DHT11_RETRIES", _py_int(item.get("retries", 5)))
    content = _replace_simple_assignment(content, "DHT11_RETRY_DELAY", _py_float(item.get("retry_delay", 0.3)))
    content = _replace_simple_assignment(content, "DHT11_OVERLAY", _py_bool(item.get("overlay")))
    content = _replace_simple_assignment(content, "DHT11_TEMP_OFFSET_C", _py_float(item.get("temp_offset_c", 0.0)))
    content = _replace_simple_assignment(content, "DHT11_HUM_OFFSET_PCT", _py_float(item.get("hum_offset_pct", 0.0)))
    content = _replace_simple_assignment(content, "DHT11_LOG_INTERVAL_MIN", _py_int(payload.get("log_interval_min", 1)))

    _write_config(content)
    return {"ok": True, "backup_path": backup_path}


def save_dht22_settings(payload):
    content = _read_config()
    backup_path = create_backup()

    mode = payload.get("mode", "single")

    if mode == "multi":
        items = payload.get("items", [])
        rendered = _render_dht22_list(items)
        content = _replace_simple_assignment(content, "DHT22_ENABLED", _py_bool(payload.get("enabled")))
        content = _replace_simple_assignment(content, "DHT22_LOG_INTERVAL_MIN", _py_int(payload.get("log_interval_min", 1)))

        if _extract_list_literal(content, "DHT22_SENSORS") is None:
            raise ValueError("DHT22_SENSORS not found in config.py")
        content = _replace_list_assignment(content, "DHT22_SENSORS", rendered)
    else:
        item = payload.get("items", [{}])[0]
        content = _replace_simple_assignment(content, "DHT22_ENABLED", _py_bool(payload.get("enabled")))
        content = _replace_simple_assignment(content, "DHT22_NAME", _py_string(item.get("name", "")))
        content = _replace_simple_assignment(content, "DHT22_GPIO_BCM", _py_int(item.get("gpio_bcm", 0)))
        content = _replace_simple_assignment(content, "DHT22_RETRIES", _py_int(item.get("retries", 5)))
        content = _replace_simple_assignment(content, "DHT22_RETRY_DELAY", _py_float(item.get("retry_delay", 0.3)))
        content = _replace_simple_assignment(content, "DHT22_OVERLAY", _py_bool(item.get("overlay")))
        content = _replace_simple_assignment(content, "DHT22_TEMP_OFFSET_C", _py_float(item.get("temp_offset_c", 0.0)))
        content = _replace_simple_assignment(content, "DHT22_HUM_OFFSET_PCT", _py_float(item.get("hum_offset_pct", 0.0)))
        content = _replace_simple_assignment(content, "DHT22_LOG_INTERVAL_MIN", _py_int(payload.get("log_interval_min", 1)))

    _write_config(content)
    return {"ok": True, "backup_path": backup_path}


def save_tsl2591_settings(payload):
    content = _read_config()
    backup_path = create_backup()

    item = payload.get("items", [{}])[0]

    content = _replace_simple_assignment(content, "TSL2591_ENABLED", _py_bool(payload.get("enabled")))
    content = _replace_simple_assignment(content, "TSL2591_NAME", _py_string(item.get("name", "")))
    content = _replace_simple_assignment(content, "TSL2591_I2C_ADDRESS", _py_address(item.get("address")))
    content = _replace_simple_assignment(content, "TSL2591_SQM2_LIMIT", _py_float(item.get("sqm2_limit", 0.0)))
    content = _replace_simple_assignment(content, "TSL2591_SQM_CORRECTION", _py_float(item.get("sqm_correction", 0.0)))
    content = _replace_simple_assignment(content, "TSL2591_OVERLAY", _py_bool(item.get("overlay")))
    content = _replace_simple_assignment(content, "TSL2591_LOG_INTERVAL_MIN", _py_int(payload.get("log_interval_min", 1)))

    _write_config(content)
    return {"ok": True, "backup_path": backup_path}

def save_mlx90614_settings(payload):
    content = _read_config()
    backup_path = create_backup()

    item = payload.get("items", [{}])[0]

    content = _replace_simple_assignment(content, "MLX90614_ENABLED", _py_bool(payload.get("enabled")))
    content = _replace_simple_assignment(content, "MLX90614_NAME", _py_string(item.get("name", "")))
    content = _replace_simple_assignment(content, "MLX90614_I2C_ADDRESS", _py_address(item.get("address", "0x5a")))
    content = _replace_simple_assignment(content, "MLX90614_AMBIENT_OFFSET_C", _py_float(item.get("ambient_offset_c", 0.0)))

    content = _replace_simple_assignment(content, "MLX_CLOUD_K1", _py_float(item.get("cloud_k1", 0.0)))
    content = _replace_simple_assignment(content, "MLX_CLOUD_K2", _py_float(item.get("cloud_k2", 0.0)))
    content = _replace_simple_assignment(content, "MLX_CLOUD_K3", _py_float(item.get("cloud_k3", 0.0)))
    content = _replace_simple_assignment(content, "MLX_CLOUD_K4", _py_float(item.get("cloud_k4", 0.0)))
    content = _replace_simple_assignment(content, "MLX_CLOUD_K5", _py_float(item.get("cloud_k5", 0.0)))
    content = _replace_simple_assignment(content, "MLX_CLOUD_K6", _py_float(item.get("cloud_k6", 0.0)))
    content = _replace_simple_assignment(content, "MLX_CLOUD_K7", _py_float(item.get("cloud_k7", 0.0)))

    content = _replace_simple_assignment(content, "MLX90614_LOG_INTERVAL_MIN", _py_int(payload.get("log_interval_min", 1)))

    _write_config(content)
    return {"ok": True, "backup_path": backup_path}

def save_htu21_settings(payload):
    content = _read_config()
    backup_path = create_backup()

    item = payload.get("items", [{}])[0]

    content = _replace_simple_assignment(content, "HTU21_ENABLED", _py_bool(payload.get("enabled")))
    content = _replace_simple_assignment(content, "HTU21_NAME", _py_string(item.get("name", "")))
    content = _replace_simple_assignment(content, "HTU21_I2C_ADDRESS", _py_address(item.get("address", "0x40"), 0x40))
    content = _replace_simple_assignment(content, "HTU21_TEMP_OFFSET", _py_float(item.get("temp_offset", 0.0)))
    content = _replace_simple_assignment(content, "HTU21_HUM_OFFSET", _py_float(item.get("hum_offset", 0.0)))
    content = _replace_simple_assignment(content, "HTU21_OVERLAY", _py_bool(item.get("overlay")))
    content = _replace_simple_assignment(content, "HTU21_LOG_INTERVAL_MIN", _py_int(payload.get("log_interval_min", 1)))

    _write_config(content)
    return {"ok": True, "backup_path": backup_path}


def save_sht3x_settings(payload):
    content = _read_config()
    backup_path = create_backup()

    item = payload.get("items", [{}])[0]

    content = _replace_simple_assignment(content, "SHT3X_ENABLED", _py_bool(payload.get("enabled")))
    content = _replace_simple_assignment(content, "SHT3X_NAME", _py_string(item.get("name", "")))
    content = _replace_simple_assignment(content, "SHT3X_I2C_ADDRESS", _py_address(item.get("address", "0x44"), 0x44))
    content = _replace_simple_assignment(content, "SHT3X_TEMP_OFFSET", _py_float(item.get("temp_offset", 0.0)))
    content = _replace_simple_assignment(content, "SHT3X_HUM_OFFSET", _py_float(item.get("hum_offset", 0.0)))
    content = _replace_simple_assignment(content, "SHT3X_OVERLAY", _py_bool(item.get("overlay")))
    content = _replace_simple_assignment(content, "SHT3X_LOG_INTERVAL_MIN", _py_int(payload.get("log_interval_min", 1)))

    _write_config(content)
    return {"ok": True, "backup_path": backup_path}