#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import types
import importlib.util
from typing import Any, Dict


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "askutils", "config.py")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _safe_get(module: Any, name: str, default: Any = None) -> Any:
    return getattr(module, name, default)


def _install_stub_modules() -> Dict[str, Any]:
    """
    Installiert temporär Stub-Module, damit config.py ohne
    Remote-Secrets-Request geladen werden kann.
    """
    backups = {}

    module_name = "askutils.utils.load_secrets"
    backups[module_name] = sys.modules.get(module_name)

    stub_module = types.ModuleType(module_name)

    def load_remote_secrets(api_key, api_url):
        return None

    stub_module.load_remote_secrets = load_remote_secrets
    sys.modules[module_name] = stub_module

    return backups


def _restore_stub_modules(backups: Dict[str, Any]) -> None:
    for module_name, original in backups.items():
        if original is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = original


def load_config_module():
    """
    Lädt askutils/config.py als Python-Modul.
    Remote-Secrets werden dabei absichtlich deaktiviert.
    """
    if not os.path.isfile(CONFIG_PATH):
        raise FileNotFoundError("config.py nicht gefunden: %s" % CONFIG_PATH)

    backups = _install_stub_modules()

    try:
        spec = importlib.util.spec_from_file_location("allsky_user_config", CONFIG_PATH)
        if spec is None or spec.loader is None:
            raise RuntimeError("config.py konnte nicht geladen werden")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        _restore_stub_modules(backups)


def load_config_data() -> Dict[str, Any]:
    module = load_config_module()

    bme280_sensors = _safe_get(module, "BME280_SENSORS", []) or []
    dht22_sensors = _safe_get(module, "DHT22_SENSORS", []) or []

    crontabs = _safe_get(module, "CRONTABS", []) or []

    data = {
        "meta": {
            "config_path": CONFIG_PATH,
            "config_exists": True,
        },

        "camera": {
            "kamera_id": _safe_get(module, "KAMERA_ID"),
            "kamera_name": _safe_get(module, "KAMERA_NAME"),
            "standort_name": _safe_get(module, "STANDORT_NAME"),
            "benutzer_name": _safe_get(module, "BENUTZER_NAME"),
            "kontakt_email": _safe_get(module, "KONTAKT_EMAIL"),
            "webseite": _safe_get(module, "WEBSEITE"),
            "latitude": _safe_get(module, "LATITUDE"),
            "longitude": _safe_get(module, "LONGITUDE"),
        },

        "system": {
            "allsky_path": _safe_get(module, "ALLSKY_PATH"),
            "image_base_path": _safe_get(module, "IMAGE_BASE_PATH"),
            "image_path": _safe_get(module, "IMAGE_PATH"),
            "image_upload_script": _safe_get(module, "IMAGE_UPLOAD_SCRIPT"),
            "nightly_upload_script": _safe_get(module, "NIGHTLY_UPLOAD_SCRIPT"),
            "indi": bool(_safe_get(module, "INDI", 0)),
            "cameraid": _safe_get(module, "CAMERAID"),
            "kamera_width": _safe_get(module, "KAMERA_WIDTH"),
            "kamera_height": _safe_get(module, "KAMERA_HEIGHT"),
        },

        "optics": {
            "pix_size_mm": _safe_get(module, "PIX_SIZE_MM"),
            "focal_mm": _safe_get(module, "FOCAL_MM"),
            "zp": _safe_get(module, "ZP"),
            "sqm_patch_size": _safe_get(module, "SQM_PATCH_SIZE"),
        },

        "uploads": {
            "image_upload_script": _safe_get(module, "IMAGE_UPLOAD_SCRIPT"),
            "nightly_upload_script": _safe_get(module, "NIGHTLY_UPLOAD_SCRIPT"),
            "config_upload_enabled": any(
                "upload_config_json" in str(job.get("command", ""))
                for job in crontabs if isinstance(job, dict)
            ),
            "image_upload_enabled": any(
                "run_image_upload" in str(job.get("command", ""))
                for job in crontabs if isinstance(job, dict)
            ),
            "nightly_upload_enabled": any(
                "run_nightly_upload" in str(job.get("command", ""))
                for job in crontabs if isinstance(job, dict)
            ),
        },

        "sensors": {
            "bme280_enabled": bool(_safe_get(module, "BME280_ENABLED", False)),
            "bme280_name": _safe_get(module, "BME280_NAME"),
            "bme280_i2c_address": _safe_get(module, "BME280_I2C_ADDRESS"),
            "bme280_overlay": _safe_get(module, "BME280_OVERLAY"),
            "bme280_temp_offset_c": _safe_get(module, "BME280_TEMP_OFFSET_C"),
            "bme280_press_offset_hpa": _safe_get(module, "BME280_PRESS_OFFSET_HPA"),
            "bme280_hum_offset_pct": _safe_get(module, "BME280_HUM_OFFSET_PCT"),
            "bme280_sensors": _safe_get(module, "BME280_SENSORS", []) or [],
            "bme280_log_interval_min": _safe_get(module, "BME280_LOG_INTERVAL_MIN"),

            "tsl2591_enabled": bool(_safe_get(module, "TSL2591_ENABLED", False)),
            "tsl2591_name": _safe_get(module, "TSL2591_NAME"),
            "tsl2591_i2c_address": _safe_get(module, "TSL2591_I2C_ADDRESS"),
            "tsl2591_overlay": _safe_get(module, "TSL2591_OVERLAY"),
            "tsl2591_sqm2_limit": _safe_get(module, "TSL2591_SQM2_LIMIT"),
            "tsl2591_sqm_correction": _safe_get(module, "TSL2591_SQM_CORRECTION"),
            "tsl2591_log_interval_min": _safe_get(module, "TSL2591_LOG_INTERVAL_MIN"),

            "ds18b20_enabled": bool(_safe_get(module, "DS18B20_ENABLED", False)),
            "ds18b20_name": _safe_get(module, "DS18B20_NAME"),
            "ds18b20_overlay": _safe_get(module, "DS18B20_OVERLAY"),
            "ds18b20_temp_offset_c": _safe_get(module, "DS18B20_TEMP_OFFSET_C"),
            "ds18b20_log_interval_min": _safe_get(module, "DS18B20_LOG_INTERVAL_MIN"),

            "dht11_enabled": bool(_safe_get(module, "DHT11_ENABLED", False)),
            "dht11_name": _safe_get(module, "DHT11_NAME"),
            "dht11_gpio_bcm": _safe_get(module, "DHT11_GPIO_BCM"),
            "dht11_retries": _safe_get(module, "DHT11_RETRIES"),
            "dht11_retry_delay": _safe_get(module, "DHT11_RETRY_DELAY"),
            "dht11_overlay": _safe_get(module, "DHT11_OVERLAY"),
            "dht11_temp_offset_c": _safe_get(module, "DHT11_TEMP_OFFSET_C"),
            "dht11_hum_offset_pct": _safe_get(module, "DHT11_HUM_OFFSET_PCT"),
            "dht11_log_interval_min": _safe_get(module, "DHT11_LOG_INTERVAL_MIN"),

            "dht22_enabled": bool(_safe_get(module, "DHT22_ENABLED", False)),
            "dht22_name": _safe_get(module, "DHT22_NAME"),
            "dht22_gpio_bcm": _safe_get(module, "DHT22_GPIO_BCM"),
            "dht22_retries": _safe_get(module, "DHT22_RETRIES"),
            "dht22_retry_delay": _safe_get(module, "DHT22_RETRY_DELAY"),
            "dht22_overlay": _safe_get(module, "DHT22_OVERLAY"),
            "dht22_temp_offset_c": _safe_get(module, "DHT22_TEMP_OFFSET_C"),
            "dht22_hum_offset_pct": _safe_get(module, "DHT22_HUM_OFFSET_PCT"),
            "dht22_sensors": _safe_get(module, "DHT22_SENSORS", []) or [],
            "dht22_log_interval_min": _safe_get(module, "DHT22_LOG_INTERVAL_MIN"),

            "mlx90614_enabled": bool(_safe_get(module, "MLX90614_ENABLED", False)),
            "mlx90614_name": _safe_get(module, "MLX90614_NAME"),
            "mlx90614_i2c_address": _safe_get(module, "MLX90614_I2C_ADDRESS"),
            "mlx90614_ambient_offset_c": _safe_get(module, "MLX90614_AMBIENT_OFFSET_C"),
            "mlx_cloud_k1": _safe_get(module, "MLX_CLOUD_K1"),
            "mlx_cloud_k2": _safe_get(module, "MLX_CLOUD_K2"),
            "mlx_cloud_k3": _safe_get(module, "MLX_CLOUD_K3"),
            "mlx_cloud_k4": _safe_get(module, "MLX_CLOUD_K4"),
            "mlx_cloud_k5": _safe_get(module, "MLX_CLOUD_K5"),
            "mlx_cloud_k6": _safe_get(module, "MLX_CLOUD_K6"),
            "mlx_cloud_k7": _safe_get(module, "MLX_CLOUD_K7"),
            "mlx90614_log_interval_min": _safe_get(module, "MLX90614_LOG_INTERVAL_MIN"),

            "htu21_enabled": bool(_safe_get(module, "HTU21_ENABLED", False)),
            "htu21_name": _safe_get(module, "HTU21_NAME"),
            "htu21_i2c_address": _safe_get(module, "HTU21_I2C_ADDRESS"),
            "htu21_temp_offset": _safe_get(module, "HTU21_TEMP_OFFSET"),
            "htu21_hum_offset": _safe_get(module, "HTU21_HUM_OFFSET"),
            "htu21_overlay": _safe_get(module, "HTU21_OVERLAY"),
            "htu21_log_interval_min": _safe_get(module, "HTU21_LOG_INTERVAL_MIN"),

            "sht3x_enabled": bool(_safe_get(module, "SHT3X_ENABLED", False)),
            "sht3x_name": _safe_get(module, "SHT3X_NAME"),
            "sht3x_i2c_address": _safe_get(module, "SHT3X_I2C_ADDRESS"),
            "sht3x_temp_offset": _safe_get(module, "SHT3X_TEMP_OFFSET"),
            "sht3x_hum_offset": _safe_get(module, "SHT3X_HUM_OFFSET"),
            "sht3x_overlay": _safe_get(module, "SHT3X_OVERLAY"),
            "sht3x_log_interval_min": _safe_get(module, "SHT3X_LOG_INTERVAL_MIN"),
        },

        "features": {
            "meteor_enabled": bool(_safe_get(module, "METEOR_ENABLE", False)),
            "meteor_output_dir": _safe_get(module, "METEOR_OUTPUT_DIR"),
            "meteor_state_file": _safe_get(module, "METEOR_STATE_FILE"),
            "meteor_keep_days_local": _safe_get(module, "METEOR_KEEP_DAYS_LOCAL"),
            "meteor_threshold": _safe_get(module, "METEOR_THRESHOLD"),
            "meteor_min_pixels": _safe_get(module, "METEOR_MIN_PIXELS"),
            "meteor_min_blob_pixels": _safe_get(module, "METEOR_MIN_BLOB_PIXELS"),
            "meteor_min_line_length": _safe_get(module, "METEOR_MIN_LINE_LENGTH"),
            "meteor_min_aspect_ratio": _safe_get(module, "METEOR_MIN_ASPECT_RATIO"),
            "meteor_fullhd_width": _safe_get(module, "METEOR_FULLHD_WIDTH"),
            "meteor_small_width": _safe_get(module, "METEOR_SMALL_WIDTH"),
            "meteor_diff_width": _safe_get(module, "METEOR_DIFF_WIDTH"),
            "meteor_boxed_width": _safe_get(module, "METEOR_BOXED_WIDTH"),
            "meteor_prev_small_width": _safe_get(module, "METEOR_PREV_SMALL_WIDTH"),
            "meteor_upload_jitter_max_seconds": _safe_get(module, "METEOR_UPLOAD_JITTER_MAX_SECONDS"),

            "kpindex_enabled": bool(_safe_get(module, "KPINDEX_ENABLED", False)),
            "kpindex_overlay": bool(_safe_get(module, "KPINDEX_OVERLAY", False)),
            "kpindex_log_interval_min": _safe_get(module, "KPINDEX_LOG_INTERVAL_MIN"),

            "analemma_enabled": bool(_safe_get(module, "ANALEMMA_ENABLED", False)),
        },
        
        "cronjobs": {
            "items": crontabs,
            "count": len(crontabs),
        }
    }

    return data


def load_config_data_safe() -> Dict[str, Any]:
    try:
        data = load_config_data()
        data["meta"]["load_ok"] = True
        data["meta"]["load_error"] = ""
        return data
    except Exception as e:
        return {
            "meta": {
                "config_path": CONFIG_PATH,
                "config_exists": os.path.isfile(CONFIG_PATH),
                "load_ok": False,
                "load_error": str(e),
            },
            "camera": {},
            "system": {},
            "optics": {},
            "uploads": {},
            "sensors": {},
            "features": {},
            "cronjobs": {"items": [], "count": 0},
        }