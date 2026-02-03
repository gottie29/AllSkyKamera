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


# ============================================================
# Influx status logging
# ============================================================
def _log_upload_status_to_influx(value: int) -> None:
    """
    measurement = uploadstatus
    tag kamera = ASKxxx
    field tjsettingsupload:
      1 = upload_ok
      2 = upload_aborted_or_failed
      3 = file_not_found
      4 = file_too_old
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
        pass


# ============================================================
# Helpers: jitter / retry
# ============================================================
def _safe_int(val, default: int) -> int:
    try:
        return int(val)
    except Exception:
        return default


def _apply_initial_jitter() -> None:
    """
    Nutzt dieselben CONFIG_UPLOAD_* Werte wie config_upload.py
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


# ============================================================
# TJ parsing
# ============================================================
def _parse_value(raw: str) -> Any:
    s = (raw or "").strip()
    if s == "":
        return ""

    low = s.lower()
    if low in ("1", "true", "yes", "on"):
        return True
    if low in ("0", "false", "no", "off"):
        return False

    try:
        if s.lstrip("-").isdigit():
            return int(s)
    except Exception:
        pass

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
            if k:
                out[k] = _parse_value(v)
    return out


def _group_day_night(flat: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    day, night, rest = {}, {}, {}
    for k, v in flat.items():
        if k.startswith("day") and k != "day":
            day[k[3:]] = v
        elif k.startswith("night") and k != "night":
            night[k[5:]] = v
        else:
            rest[k] = v
    return {"day": day, "night": night, "rest": rest}


def _parse_latlon_deg(val: Any) -> Optional[float]:
    try:
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)

        s = str(val).strip()
        if not s:
            return None

        hemi = s[-1].upper()
        if hemi in ("N", "S", "E", "W"):
            num = float(s[:-1])
            if hemi in ("S", "W"):
                num = -abs(num)
            return float(num)

        return float(s)
    except Exception:
        return None


# ============================================================
# Paths
# ============================================================
def _tj_capture_args_path() -> str:
    allsky = getattr(config, "ALLSKY_PATH", "/home/pi/allsky")
    tmpdir = getattr(config, "IMAGE_PATH", "tmp")
    return os.path.join(str(allsky), str(tmpdir), "capture_args.txt")


def _tj_settings_json_path() -> str:
    allsky = getattr(config, "ALLSKY_PATH", "/home/pi/allsky")
    return os.path.join(str(allsky), "config", "settings.json")


# ============================================================
# Sanitizing / Whitelist
# ============================================================
def _sanitize(flat: Dict[str, Any]) -> Dict[str, Any]:
    """
    Exportiert ALLE Settings und gruppiert in:
      - day
      - night
      - timelapse
      - keogram
      - startrails
      - remote
      - overlay
      - ui
      - image (fallback / rest)

    Day/Night keys werden ohne Prefix gespeichert:
      dayautoexposure -> day.autoexposure
      nightgain       -> night.gain

    Außerdem:
      imagestretchamountdaytime/imagestretchmidpointdaytime -> day.imagestretchamount / imagestretchmidpoint
      imagestretchamountnighttime/imagestretchmidpointnighttime -> night.imagestretchamount / imagestretchmidpoint
    """

    day: Dict[str, Any] = {}
    night: Dict[str, Any] = {}

    timelapse: Dict[str, Any] = {}
    keogram: Dict[str, Any] = {}
    startrails: Dict[str, Any] = {}
    remote: Dict[str, Any] = {}
    overlay: Dict[str, Any] = {}
    ui: Dict[str, Any] = {}

    image: Dict[str, Any] = {}  # fallback

    def put(group: Dict[str, Any], key: str, value: Any) -> None:
        group[key] = value

    for k, v in flat.items():
        if not isinstance(k, str):
            continue

        # -----------------------
        # Day / Night
        # -----------------------
        if k.startswith("day") and k != "day":
            put(day, k[3:], v)
            continue

        if k.startswith("night") and k != "night":
            put(night, k[5:], v)
            continue

        # Stretch (gehört logisch zu Day/Night)
        if k in ("imagestretchamountdaytime", "imagestretchmidpointdaytime"):
            put(day, k.replace("daytime", ""), v)  # imagestretchamount / imagestretchmidpoint
            continue

        if k in ("imagestretchamountnighttime", "imagestretchmidpointnighttime"):
            put(night, k.replace("nighttime", ""), v)
            continue

        # -----------------------
        # Timelapse (inkl. MiniTimelapse)
        # -----------------------
        if k.startswith("timelapse") or k.startswith("minitimelapse"):
            put(timelapse, k, v)
            continue

        # -----------------------
        # Keogram
        # -----------------------
        if k.startswith("keogram"):
            put(keogram, k, v)
            continue

        # -----------------------
        # Startrails
        # -----------------------
        if k.startswith("startrails") or k.startswith("startrail"):
            put(startrails, k, v)
            continue

        # -----------------------
        # Remote / Upload Targets
        # -----------------------
        if (
            k.startswith("remotewebsite")
            or k.startswith("remoteserver")
            or k.startswith("useremote")
            or k.startswith("uselocalwebsite")
            or k.startswith("uselogin")  # eher UI, aber hängt oft mit remote webui zusammen -> wir packen es unten in UI
        ):
            # uselogin lassen wir in UI (siehe unten), deshalb hier ausklammern:
            if k == "uselogin":
                pass
            else:
                put(remote, k, v)
                continue

        # -----------------------
        # Overlay / Texte / Fonts / Anzeige
        # -----------------------
        if k in (
            "overlaymethod",
            "showtime", "showtemp", "showexposure", "showgain", "showmean", "showfocus",
            "text", "extratext", "extratextage",
            "textlineheight", "textx", "texty",
            "fontname", "fontcolor", "smallfontcolor",
            "fonttype", "fontsize", "fontline", "outlinefont",
            "daytimeoverlay", "nighttimeoverlay",
            "temptype", "timeformat",
        ):
            put(overlay, k, v)
            continue

        # -----------------------
        # UI / Meta (WebUI, Locale, Hardware-Infos, Map)
        # -----------------------
        if k in (
            "displaysettings",
            "imagessortorder",
            "showupdatedmessage",
            "uselogin",
            "webuidatafiles",
            "locale",
            "lastchanged",
            "showonmap",
            "location",
            "owner",
            "camera",
            "lens",
            "computer",
            "equipmentinfo",
            "cameratype",
            "cameramodel",
            "cameranumber",
        ):
            put(ui, k, v)
            continue

        # -----------------------
        # Fallback: bleibt in image
        # -----------------------
        put(image, k, v)

    out: Dict[str, Any] = {}

    if day:
        out["day"] = {kk: day[kk] for kk in sorted(day.keys())}
    if night:
        out["night"] = {kk: night[kk] for kk in sorted(night.keys())}

    if timelapse:
        out["timelapse"] = {kk: timelapse[kk] for kk in sorted(timelapse.keys())}
    if keogram:
        out["keogram"] = {kk: keogram[kk] for kk in sorted(keogram.keys())}
    if startrails:
        out["startrails"] = {kk: startrails[kk] for kk in sorted(startrails.keys())}
    if remote:
        out["remote"] = {kk: remote[kk] for kk in sorted(remote.keys())}
    if overlay:
        out["overlay"] = {kk: overlay[kk] for kk in sorted(overlay.keys())}
    if ui:
        out["ui"] = {kk: ui[kk] for kk in sorted(ui.keys())}

    if image:
        out["image"] = {kk: image[kk] for kk in sorted(image.keys())}

    return out

# ============================================================
# Payload builder
# ============================================================
def build_payload(flat: Dict[str, Any], source_file: str, sources: list) -> Dict[str, Any]:
    kamera_id = getattr(config, "KAMERA_ID", None) or getattr(config, "KAMERA", None) or ""
    ts = int(time.time())

    payload: Dict[str, Any] = {
        "schema": "allskykamera.tjsettings.v1",
        "kamera": str(kamera_id),
        "source": "TJ",
        "generated_at": ts,
        "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(ts)),
        "file": os.path.basename(source_file),
        "sources": sources,
        "settings": _sanitize(flat),
    }

    if "version" in flat:
        payload["tj_version"] = str(flat.get("version"))

    lat = _parse_latlon_deg(flat.get("latitude"))
    lon = _parse_latlon_deg(flat.get("longitude"))
    if lat is not None:
        payload["latitude_deg"] = round(lat, 6)
    if lon is not None:
        payload["longitude_deg"] = round(lon, 6)

    return payload


# ============================================================
# Public API
# ============================================================
def create_tj_settings_json(filename: str = "tj_settings.json") -> Optional[str]:
    src_args = _tj_capture_args_path()
    src_json = _tj_settings_json_path()

    flat_args = None
    flat_json = None
    sources = []

    if os.path.isfile(src_args):
        flat_args = _parse_tj_keyval_file(src_args)
        sources.append({"type": "capture_args", "file": src_args})

    if os.path.isfile(src_json):
        try:
            with open(src_json, "r", encoding="utf-8", errors="replace") as f:
                flat_json = json.load(f)
            if isinstance(flat_json, dict):
                sources.append({"type": "settings_json", "file": src_json})
        except Exception as e:
            error(f"tj_settings_upload settings_json_read_failed error={e}")

    if not flat_args and not flat_json:
        error("tj_settings_upload no_sources_found")
        _log_upload_status_to_influx(3)
        return None

    flat: Dict[str, Any] = {}
    if isinstance(flat_args, dict):
        flat.update(flat_args)
    if isinstance(flat_json, dict):
        flat.update(flat_json)

    try:
        source_file = src_json if flat_json else src_args
        payload = build_payload(flat, source_file, sources)

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=4, sort_keys=True)

        log(f"tj_settings_upload created_json file={filename}")
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
    missing = []
    for k in ("FTP_SERVER", "FTP_USER", "FTP_PASS", "FTP_REMOTE_DIR"):
        if not hasattr(config, k) or not getattr(config, k):
            missing.append(k)

    if missing:
        error(f"tj_settings_upload aborted: missing {', '.join(missing)}")
        _log_upload_status_to_influx(2)
        return False

    if not filepath or not os.path.isfile(filepath):
        error(f"tj_settings_upload file not found: {filepath}")
        _log_upload_status_to_influx(3)
        return False

    max_age = _safe_int(getattr(config, "CONFIG_UPLOAD_MAX_AGE_SECONDS", 0), 0)
    if max_age > 0:
        try:
            if time.time() - os.path.getmtime(filepath) > max_age:
                _log_upload_status_to_influx(4)
                return False
        except Exception:
            pass

    _apply_initial_jitter()

    max_retries = _safe_int(getattr(config, "CONFIG_UPLOAD_MAX_RETRIES", 3), 3)
    retry_min_s = _safe_int(getattr(config, "CONFIG_UPLOAD_RETRY_MIN_SECONDS", 120), 120)
    retry_max_s = _safe_int(getattr(config, "CONFIG_UPLOAD_RETRY_MAX_SECONDS", 300), 300)
    retry_max_s = max(retry_min_s, retry_max_s)

    attempt = 0
    while True:
        attempt += 1
        try:
            _upload_once(filepath)
            log(f"tj_settings_upload upload_ok attempt={attempt}")
            _log_upload_status_to_influx(1)
            return True
        except Exception as e:
            error(f"tj_settings_upload upload_fail attempt={attempt} error={e}")
            if attempt > max_retries:
                _log_upload_status_to_influx(2)
                return False
            _sleep_retry_window(retry_min_s, retry_max_s)
