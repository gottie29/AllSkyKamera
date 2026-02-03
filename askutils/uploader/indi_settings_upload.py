# askutils/uploader/indi_settings_upload.py
# -*- coding: utf-8 -*-

import os
import time
import random
import json
import ftplib
import subprocess
from copy import deepcopy
from typing import Optional, Any

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
    field indisettingsupload:
      1 = upload_ok
      2 = upload_aborted_or_failed
      3 = file_not_found_or_dump_failed
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
            {"indisettingsupload": float(value)},
            tags={"host": "host1", "kamera": str(kamera_id)},
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
    max_s = _safe_int(getattr(config, "CONFIG_UPLOAD_JITTER_MAX_SECONDS", 180), 180)
    if max_s <= 0:
        return
    delay = random.randint(0, max_s)
    if delay > 0:
        log(f"indi_settings_upload jitter_seconds={delay}")
        time.sleep(delay)


def _sleep_retry_window(min_s: int = 120, max_s: int = 300) -> int:
    delay = random.randint(min_s, max_s)
    log(f"indi_settings_upload retry_sleep_seconds={delay}")
    time.sleep(delay)
    return delay


# ============================================================
# INDI config dump
# ============================================================
def _indi_allsky_config_py() -> str:
    """
    Pfad zum INDI-allsky config.py, ohne Hardcoding auf /home/pi.
    Priorität:
      1) config.INDI_ALLSKY_CONFIG_PY (wenn gesetzt)
      2) ~/indi-allsky/config.py
      3) /home/pi/indi-allsky/config.py (nur als letzter Legacy-Fallback)
    """
    # 1) explizit aus deiner askutils/config.py
    p = getattr(config, "INDI_ALLSKY_CONFIG_PY", "") or ""
    p = str(p).strip()
    if p:
        return os.path.realpath(os.path.expanduser(p))

    # 2) Home des aktuellen Users
    home = os.path.expanduser("~")
    cand = os.path.join(home, "indi-allsky", "config.py")
    if os.path.isfile(cand):
        return os.path.realpath(cand)

    # 3) Legacy fallback (falls jemand doch noch pi nutzt)
    return "/home/pi/indi-allsky/config.py"

def _run_indi_dump() -> str:
    cfg_py = _indi_allsky_config_py()

    if not os.path.isfile(cfg_py):
        raise FileNotFoundError(cfg_py)

    cmd = [cfg_py, "dump"]

    prefix = getattr(config, "INDI_ALLSKY_CONFIG_CMD_PREFIX", "") or ""
    if prefix.strip():
        cmd = [prefix.strip()] + cmd

    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
        check=False,
    )

    if proc.returncode != 0:
        raise RuntimeError(
            f"dump_failed rc={proc.returncode} stderr={proc.stderr.strip()[:400]}"
        )

    out = (proc.stdout or "").strip()
    if not out:
        raise RuntimeError("dump_empty_stdout")

    if not out.startswith("{"):
        raise RuntimeError(f"dump_not_json_like head={out[:80]!r}")

    return out


def _atomic_write(path: str, content: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)


# ============================================================
# Sanitizing / Blacklist
# ============================================================

# Einzelne Top-Level Keys entfernen
_BLACKLIST_TOPLEVEL_KEYS = {
    "INDI_SERVER",
    "INDI_PORT",
    "WEB_STATUS_TEMPLATE",
    "VARLIB_FOLDER",
    "URL_TEMPLATE",
    "IMAGE_FOLDER",
    "IMAGE_LABEL_TEMPLATE",
    "IMAGE_EXPORT_FOLDER",
    "DUMP1090_URL",
}

# Ganze Top-Level Blöcke entfernen
_BLACKLIST_TOPLEVEL_BLOCKS = {
    "FILETRANSFER",
    "S3UPLOAD",
    "MQTTPUBLISH",
    "SYNCAPI",
    "YOUTUBE",
}

# Secrets / Credentials
_SECRET_KEYWORDS = (
    "password",
    "passwd",
    "secret",
    "apikey",
    "api_key",
    "token",
    "private_key",
    "public_key",
    "creds",
    "secrets_file",
)


def _is_blacklisted_key(key: str) -> bool:
    ku = key.upper()
    kl = key.lower()

    if ku.startswith("MQTT_") or "MQTT_" in ku:
        return True

    # explizite Top-Level Keys
    if ku in _BLACKLIST_TOPLEVEL_KEYS:
        return True

    # alle Ports raus
    if "PORT" in ku:
        return True

    # Secrets
    if any(s in kl for s in _SECRET_KEYWORDS):
        return True

    # encrypted blobs
    if kl.endswith("_e"):
        return True

    return False


def sanitize_indi_dump(cfg: Any) -> Any:
    """
    Entfernt:
    - explizite Top-Level Keys
    - komplette Top-Level Blöcke
    - alle *PORT* Keys (global)
    - Secrets / *_E
    Lat / Long bleiben erhalten.
    """
    def walk(obj, *, is_root=False):
        if isinstance(obj, dict):
            newd = {}
            for k, v in obj.items():
                if not isinstance(k, str):
                    continue

                # komplette Top-Level Blöcke
                if is_root and k in _BLACKLIST_TOPLEVEL_BLOCKS:
                    continue

                # einzelne Keys
                if _is_blacklisted_key(k):
                    continue

                newd[k] = walk(v, is_root=False)
            return newd

        if isinstance(obj, list):
            return [walk(x, is_root=False) for x in obj]

        return obj

    return walk(deepcopy(cfg), is_root=True)


# ============================================================
# Public API
# ============================================================
def create_indi_settings_json(filename: str = "indi_settings.json") -> Optional[str]:
    """
    Erzeugt indi_settings.json via ~/indi-allsky/config.py dump,
    filtert Blacklist + Secrets und schreibt ein sauberes JSON.
    """
    try:
        dumped = _run_indi_dump()

        try:
            cfg = json.loads(dumped)
        except Exception as e:
            raise RuntimeError(f"dump_json_parse_failed error={e}")

        clean = sanitize_indi_dump(cfg)

        kamera_id = getattr(config, "KAMERA_ID", None) or getattr(config, "KAMERA", None) or ""
        ts = int(time.time())

        payload = {
            "meta": {
                "schema": "allskykamera.indisettings.v1",
                "kamera": str(kamera_id),
                "source": "INDI",
                "generated_at": ts,
                "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(ts)),
            },
            "config": clean,
        }

        _atomic_write(filename, json.dumps(payload, ensure_ascii=False, indent=2))
        log(f"indi_settings_upload created_json file={filename}")
        return filename

    except Exception as e:
        error(f"indi_settings_upload create_json_failed error={e}")
        _log_upload_status_to_influx(3)
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
        error(f"indi_settings_upload aborted: missing {', '.join(missing)}")
        _log_upload_status_to_influx(2)
        return False

    if not filepath or not os.path.isfile(filepath):
        error(f"indi_settings_upload file not found: {filepath}")
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
            log(f"indi_settings_upload upload_ok attempt={attempt}")
            _log_upload_status_to_influx(1)
            return True
        except Exception as e:
            error(f"indi_settings_upload upload_fail attempt={attempt} error={e}")
            if attempt > max_retries:
                _log_upload_status_to_influx(2)
                return False
            _sleep_retry_window(retry_min_s, retry_max_s)
