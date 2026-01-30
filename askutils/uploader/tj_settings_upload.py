# askutils/uploader/tj_settings_upload.py
# -*- coding: utf-8 -*-

import json
import os
import time
import random
import ftplib
from typing import Any, Dict, Optional

from askutils import config
from askutils.utils.logger import log, error

# Influx Writer (wie bei raspi_status)
try:
    from askutils.utils import influx_writer
except Exception:
    influx_writer = None


# -----------------------------
# Influx status logging
# -----------------------------
def _log_upload_status_to_influx(value: int) -> None:
    """
    measurement = uploadstatus
    tag kamera = ASKxxx
    field tjsettingsupload:
      1 = upload_ok
      2 = upload_aborted_or_failed
      3 = file_not_found
      4 = file_too_old (optional)
    """
    try:
        if influx_writer is None:
            return

        kamera_id = getattr(config, "KAMERA_ID", None) or getattr(config, "KAMERA", None)
        if not kamera_id:
            return

        influx_writer.log_metric(
            "uploadstatus",
            {"tjsettingsupload": float(value)},
            tags={"host": "host1", "kamera": str(kamera_id)}
        )
    except Exception:
        # Logging darf nie den Export abbrechen
        pass


# -----------------------------
# Helpers: jitter/retry (wie config_upload)
# -----------------------------
def _safe_int(val, default: int) -> int:
    try:
        return int(val)
    except Exception:
        return default


def _apply_initial_jitter() -> None:
    """
    Jitter vor dem Upload, um gleichzeitige Peaks zu vermeiden.
    Wir nehmen bewusst dieselbe Config wie config_upload (CONFIG_UPLOAD_JITTER_MAX_SECONDS),
    damit du keine neuen Settings brauchst.
    Default: 180 Sekunden
    """
    max_s = _safe_int(getattr(config, "CONFIG_UPLOAD_JITTER_MAX_SECONDS", 180), 180)
    if max_s <= 0:
        return

    delay = random.randint(0, max_s)
    if delay > 0:
        log(f"tj_settings_upload jitter_seconds={delay}")
        time.sleep(delay)


def _sleep_retry_window(min_s: int = 120, max_s: int = 300) -> int:
    delay = random.randint(min_s, max_s)
    log(f"tj_settings_upload retry_sleep_seconds={delay}")
    time.sleep(delay)
    return delay


# -----------------------------
# TJ parsing
# -----------------------------
def _parse_value(raw: str) -> Any:
    s = (raw or "").strip()
    if s == "":
        return ""

    low = s.lower()
    if low in ("1", "true", "yes", "on"):
        return True
    if low in ("0", "false", "no", "off"):
        return False

    # int?
    try:
        if s.lstrip("-").isdigit():
            return int(s)
    except Exception:
        pass

    # float?
    try:
        if "." in s:
            return float(s)
    except Exception:
        pass

    return s


def _parse_tj_keyval_file(path: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            if not k:
                continue
            out[k] = _parse_value(v)
    return out


def _group_day_night(flat: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    day: Dict[str, Any] = {}
    night: Dict[str, Any] = {}
    rest: Dict[str, Any] = {}

    for k, v in flat.items():
        if k.startswith("day") and k != "day":
            day[k[3:]] = v
        elif k.startswith("night") and k != "night":
            night[k[5:]] = v
        else:
            rest[k] = v

    return {"day": day, "night": night, "rest": rest}


def _sanitize(flat: Dict[str, Any]) -> Dict[str, Any]:
    """
    Public-Whitelist für Steckbrief.

    Absichtlich NICHT:
    - save_dir, filename, extraargs, text, extratext, debuglevel, timeformat etc.
    """
    g = _group_day_night(flat)
    day = g["day"]
    night = g["night"]
    rest = g["rest"]

    day_keep = {
        "autoexposure", "maxautoexposure", "exposure", "mean", "meanthreshold",
        "delay", "autogain", "maxautogain", "gain", "bin", "awb", "wbr", "wbb",
        "skipframes", "tuningfile",
    }
    night_keep = set(day_keep)

    rest_keep = {
        "takedaytimeimages", "takenighttimeimages",
        "saturation", "contrast", "sharpness",
        "type", "quality",
        "rotation", "flip",
        "determinefocus", "consistentdelays",
        "angle",
        "takedarkframes",
        "overlaymethod",
        "showtime", "showtemp", "showexposure", "showgain", "showmean", "showfocus",
        "textlineheight", "textx", "texty",
        "fontname", "fontcolor", "smallfontcolor", "fonttype", "fontsize",
        "fontline", "outlinefont",
        "version",
        # NEU: Koordinaten aus TJ mit exportieren
        "latitude", "longitude",
    }

    out: Dict[str, Any] = {
        "day": {k: day[k] for k in sorted(day.keys()) if k in day_keep},
        "night": {k: night[k] for k in sorted(night.keys()) if k in night_keep},
        "imaging": {k: rest[k] for k in sorted(rest.keys()) if k in rest_keep},
    }

    return {k: v for k, v in out.items() if v}

def _parse_latlon_deg(s: Any) -> Optional[float]:
    """
    Convert TJ format like '52.503N', '13.499E', '61.0', '-150' to float degrees.
    Returns None if parsing fails.
    """
    try:
        if s is None:
            return None
        if isinstance(s, (int, float)):
            return float(s)

        txt = str(s).strip()
        if not txt:
            return None

        # last char may be N/S/E/W
        hemi = txt[-1].upper()
        if hemi in ("N", "S", "E", "W"):
            num = float(txt[:-1])
            if hemi in ("S", "W"):
                num = -abs(num)
            return float(num)

        # plain numeric string
        return float(txt)
    except Exception:
        return None


def _tj_capture_args_path() -> str:
    """
    Nutzt vorhandene config-Werte (keine neuen Settings):
    ALLSKY_PATH + IMAGE_PATH + capture_args.txt
    Default wie bei dir: /home/pi/allsky/tmp/capture_args.txt
    """
    allsky = getattr(config, "ALLSKY_PATH", "/home/pi/allsky")
    tmpdir = getattr(config, "IMAGE_PATH", "tmp")  # bei dir "tmp"
    return os.path.join(str(allsky), str(tmpdir), "capture_args.txt")


def build_payload(flat: Dict[str, Any], source_file: str) -> Dict[str, Any]:
    kamera_id = getattr(config, "KAMERA_ID", None) or getattr(config, "KAMERA", None) or ""
    ts = int(time.time())

    payload: Dict[str, Any] = {
        "schema": "allskykamera.tjsettings.v1",
        "kamera": str(kamera_id),
        "source": "TJ",
        "generated_at": ts,
        "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(ts)),
        "file": os.path.basename(source_file),
    }

    if "version" in flat:
        payload["tj_version"] = str(flat.get("version"))

    payload["settings"] = _sanitize(flat)
    # NEU: lat/lon zusätzlich als float (deg) anbieten
    try:
        lat_raw = flat.get("latitude")
        lon_raw = flat.get("longitude")
        lat_deg = _parse_latlon_deg(lat_raw)
        lon_deg = _parse_latlon_deg(lon_raw)
        if lat_deg is not None:
            payload["latitude_deg"] = round(lat_deg, 6)
        if lon_deg is not None:
            payload["longitude_deg"] = round(lon_deg, 6)
    except Exception:
        pass
    
    return payload


# -----------------------------
# Public API like config_upload
# -----------------------------
def create_tj_settings_json(filename: str = "tj_settings.json") -> Optional[str]:
    src = _tj_capture_args_path()
    if not os.path.isfile(src):
        error(f"tj_settings_upload source_file_not_found file={src}")
        _log_upload_status_to_influx(3)
        return None

    try:
        flat = _parse_tj_keyval_file(src)
        payload = build_payload(flat, source_file=src)

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=4, sort_keys=True)

        log(f"tj_settings_upload created_json file={filename} source={src}")
        return filename
    except Exception as e:
        error(f"tj_settings_upload create_json_failed error={e}")
        return None


def _upload_once(filepath: str) -> None:
    with ftplib.FTP(config.FTP_SERVER) as ftp:
        try:
            ftp.connect(host=config.FTP_SERVER, timeout=30)
            ftp.login(config.FTP_USER, config.FTP_PASS)
        except TypeError:
            ftp.login(config.FTP_USER, config.FTP_PASS)

        ftp.cwd(config.FTP_REMOTE_DIR)
        with open(filepath, "rb") as f:
            ftp.storbinary(f"STOR {os.path.basename(filepath)}", f)


def upload_to_ftp(filepath: str) -> bool:
    """
    Upload wie config_upload:
    - nutzt CONFIG_UPLOAD_* Werte (keine neuen Settings)
    - jitter + retry
    """
    missing = []
    for k in ("FTP_SERVER", "FTP_USER", "FTP_PASS", "FTP_REMOTE_DIR"):
        if not hasattr(config, k) or not getattr(config, k):
            missing.append(k)

    if missing:
        error(f"tj_settings_upload abgebrochen: config-Werte fehlen/leer: {', '.join(missing)}")
        _log_upload_status_to_influx(2)
        return False

    if not filepath or not os.path.isfile(filepath):
        error(f"tj_settings_upload abgebrochen: Datei nicht gefunden: {filepath}")
        _log_upload_status_to_influx(3)
        return False

    # Optional "zu alt" – nutzt dieselbe config wie config_upload, damit keine neuen Settings nötig sind
    max_age = _safe_int(getattr(config, "CONFIG_UPLOAD_MAX_AGE_SECONDS", 0), 0)
    if max_age > 0:
        try:
            age = time.time() - os.path.getmtime(filepath)
            if age > max_age:
                error(f"tj_settings_upload file_too_old age_seconds={int(age)} max_age_seconds={max_age} file={filepath}")
                _log_upload_status_to_influx(4)
                return False
        except Exception:
            pass

    _apply_initial_jitter()

    max_retries = _safe_int(getattr(config, "CONFIG_UPLOAD_MAX_RETRIES", 3), 3)
    retry_min_s = _safe_int(getattr(config, "CONFIG_UPLOAD_RETRY_MIN_SECONDS", 120), 120)
    retry_max_s = _safe_int(getattr(config, "CONFIG_UPLOAD_RETRY_MAX_SECONDS", 300), 300)
    if retry_max_s < retry_min_s:
        retry_max_s = retry_min_s

    attempt = 0
    while True:
        attempt += 1
        try:
            _upload_once(filepath)
            log(f"tj_settings_upload upload_ok attempt={attempt} file={os.path.basename(filepath)} remote_dir={config.FTP_REMOTE_DIR}")
            _log_upload_status_to_influx(1)
            return True
        except Exception as e:
            error(f"tj_settings_upload upload_fail attempt={attempt} error={e}")

            if attempt > max_retries:
                error(f"tj_settings_upload giving_up attempts={attempt} max_retries={max_retries}")
                _log_upload_status_to_influx(2)
                return False

            _sleep_retry_window(retry_min_s, retry_max_s)
