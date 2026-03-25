#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Any, Dict, List


def _bool(v: Any) -> bool:
    return bool(v)


def _hex_or_none(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, int):
        return hex(v)
    return str(v)


def _normalize_multi_items(items: Any) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []

    out = []
    for item in items:
        if isinstance(item, dict):
            out.append(dict(item))
    return out


def _single_item(**kwargs) -> List[Dict[str, Any]]:
    return [kwargs]


def build_sensor_overview(config_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    sensors = config_data.get("sensors", {})

    overview: List[Dict[str, Any]] = []

    # --------------------------------------------------
    # BME280
    # --------------------------------------------------
    bme_multi = _normalize_multi_items(sensors.get("bme280_sensors", []))
    if bme_multi:
        bme_items = []
        for item in bme_multi:
            bme_items.append({
                "enabled": _bool(item.get("enabled")),
                "name": item.get("name", ""),
                "address": _hex_or_none(item.get("address")),
                "overlay": _bool(item.get("overlay")),
                "temp_offset_c": item.get("temp_offset_c", 0.0),
                "press_offset_hpa": item.get("press_offset_hpa", 0.0),
                "hum_offset_pct": item.get("hum_offset_pct", 0.0),
            })
        bme_mode = "multi"
    else:
        bme_items = _single_item(
            enabled=_bool(sensors.get("bme280_enabled")),
            name=sensors.get("bme280_name", ""),
            address=_hex_or_none(sensors.get("bme280_i2c_address")),
            overlay=_bool(sensors.get("bme280_overlay")),
            temp_offset_c=sensors.get("bme280_temp_offset_c", 0.0),
            press_offset_hpa=sensors.get("bme280_press_offset_hpa", 0.0),
            hum_offset_pct=sensors.get("bme280_hum_offset_pct", 0.0),
        )
        bme_mode = "single"

    overview.append({
        "key": "bme280",
        "title": "BME280",
        "enabled": _bool(sensors.get("bme280_enabled")),
        "mode": bme_mode,
        "count": len(bme_items),
        "log_interval_min": sensors.get("bme280_log_interval_min"),
        "items": bme_items,
    })

    # --------------------------------------------------
    # TSL2591
    # --------------------------------------------------
    overview.append({
        "key": "tsl2591",
        "title": "TSL2591",
        "enabled": _bool(sensors.get("tsl2591_enabled")),
        "mode": "single",
        "count": 1,
        "log_interval_min": sensors.get("tsl2591_log_interval_min"),
        "items": _single_item(
            enabled=_bool(sensors.get("tsl2591_enabled")),
            name=sensors.get("tsl2591_name", ""),
            address=_hex_or_none(sensors.get("tsl2591_i2c_address")),
            overlay=_bool(sensors.get("tsl2591_overlay")),
            sqm2_limit=sensors.get("tsl2591_sqm2_limit", 0.0),
            sqm_correction=sensors.get("tsl2591_sqm_correction", 0.0),
        ),
    })

    # --------------------------------------------------
    # DS18B20
    # --------------------------------------------------
    overview.append({
        "key": "ds18b20",
        "title": "DS18B20",
        "enabled": _bool(sensors.get("ds18b20_enabled")),
        "mode": "single",
        "count": 1,
        "log_interval_min": sensors.get("ds18b20_log_interval_min"),
        "items": _single_item(
            enabled=_bool(sensors.get("ds18b20_enabled")),
            name=sensors.get("ds18b20_name", ""),
            overlay=_bool(sensors.get("ds18b20_overlay")),
            temp_offset_c=sensors.get("ds18b20_temp_offset_c", 0.0),
        ),
    })

    # --------------------------------------------------
    # DHT11
    # --------------------------------------------------
    overview.append({
        "key": "dht11",
        "title": "DHT11",
        "enabled": _bool(sensors.get("dht11_enabled")),
        "mode": "single",
        "count": 1,
        "log_interval_min": sensors.get("dht11_log_interval_min"),
        "items": _single_item(
            enabled=_bool(sensors.get("dht11_enabled")),
            name=sensors.get("dht11_name", ""),
            gpio_bcm=sensors.get("dht11_gpio_bcm"),
            retries=sensors.get("dht11_retries"),
            retry_delay=sensors.get("dht11_retry_delay"),
            overlay=_bool(sensors.get("dht11_overlay")),
            temp_offset_c=sensors.get("dht11_temp_offset_c", 0.0),
            hum_offset_pct=sensors.get("dht11_hum_offset_pct", 0.0),
        ),
    })

    # --------------------------------------------------
    # DHT22
    # --------------------------------------------------
    dht22_multi = _normalize_multi_items(sensors.get("dht22_sensors", []))
    if dht22_multi:
        dht22_items = []
        for item in dht22_multi:
            dht22_items.append({
                "enabled": _bool(item.get("enabled")),
                "name": item.get("name", ""),
                "gpio_bcm": item.get("gpio_bcm"),
                "retries": item.get("retries"),
                "retry_delay": item.get("retry_delay"),
                "overlay": _bool(item.get("overlay")),
                "temp_offset_c": item.get("temp_offset_c", 0.0),
                "hum_offset_pct": item.get("hum_offset_pct", 0.0),
            })
        dht22_mode = "multi"
    else:
        dht22_items = _single_item(
            enabled=_bool(sensors.get("dht22_enabled")),
            name=sensors.get("dht22_name", ""),
            gpio_bcm=sensors.get("dht22_gpio_bcm"),
            retries=sensors.get("dht22_retries"),
            retry_delay=sensors.get("dht22_retry_delay"),
            overlay=_bool(sensors.get("dht22_overlay")),
            temp_offset_c=sensors.get("dht22_temp_offset_c", 0.0),
            hum_offset_pct=sensors.get("dht22_hum_offset_pct", 0.0),
        )
        dht22_mode = "single"

    overview.append({
        "key": "dht22",
        "title": "DHT22",
        "enabled": _bool(sensors.get("dht22_enabled")),
        "mode": dht22_mode,
        "count": len(dht22_items),
        "log_interval_min": sensors.get("dht22_log_interval_min"),
        "items": dht22_items,
    })

    # --------------------------------------------------
    # MLX90614
    # --------------------------------------------------
    overview.append({
        "key": "mlx90614",
        "title": "MLX90614",
        "enabled": _bool(sensors.get("mlx90614_enabled")),
        "mode": "single",
        "count": 1,
        "log_interval_min": sensors.get("mlx90614_log_interval_min"),
        "items": _single_item(
            enabled=_bool(sensors.get("mlx90614_enabled")),
            name=sensors.get("mlx90614_name", ""),
            address=_hex_or_none(sensors.get("mlx90614_i2c_address")),
            ambient_offset_c=sensors.get("mlx90614_ambient_offset_c", 0.0),
            cloud_k1=sensors.get("mlx_cloud_k1", 0.0),
            cloud_k2=sensors.get("mlx_cloud_k2", 0.0),
            cloud_k3=sensors.get("mlx_cloud_k3", 0.0),
            cloud_k4=sensors.get("mlx_cloud_k4", 0.0),
            cloud_k5=sensors.get("mlx_cloud_k5", 0.0),
            cloud_k6=sensors.get("mlx_cloud_k6", 0.0),
            cloud_k7=sensors.get("mlx_cloud_k7", 0.0),
        ),
    })

    # --------------------------------------------------
    # HTU21
    # --------------------------------------------------
    overview.append({
        "key": "htu21",
        "title": "HTU21 / GY-21",
        "enabled": _bool(sensors.get("htu21_enabled")),
        "mode": "single",
        "count": 1,
        "log_interval_min": sensors.get("htu21_log_interval_min"),
        "items": _single_item(
            enabled=_bool(sensors.get("htu21_enabled")),
            name=sensors.get("htu21_name", ""),
            address=_hex_or_none(sensors.get("htu21_i2c_address")),
            overlay=_bool(sensors.get("htu21_overlay")),
            temp_offset=sensors.get("htu21_temp_offset", 0.0),
            hum_offset=sensors.get("htu21_hum_offset", 0.0),
        ),
    })

    # --------------------------------------------------
    # SHT3X
    # --------------------------------------------------
    overview.append({
        "key": "sht3x",
        "title": "SHT3X",
        "enabled": _bool(sensors.get("sht3x_enabled")),
        "mode": "single",
        "count": 1,
        "log_interval_min": sensors.get("sht3x_log_interval_min"),
        "items": _single_item(
            enabled=_bool(sensors.get("sht3x_enabled")),
            name=sensors.get("sht3x_name", ""),
            address=_hex_or_none(sensors.get("sht3x_i2c_address")),
            overlay=_bool(sensors.get("sht3x_overlay")),
            temp_offset=sensors.get("sht3x_temp_offset", 0.0),
            hum_offset=sensors.get("sht3x_hum_offset", 0.0),
        ),
    })

    return overview