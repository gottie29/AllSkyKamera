# askutils/sensors/heater.py
import os
import json
import time
import math
import datetime
from typing import Optional, Dict, Tuple

try:
    import RPi.GPIO as GPIO
except Exception:  # allow import on non-RPi for dev/testing
    GPIO = None

from .. import config


# -----------------------------
# Time + JSON helpers (UTC)
# -----------------------------
def iso_now_utc() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def parse_ts_utc(ts: str) -> datetime.datetime:
    ts = (ts or "").strip()
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def read_json(path: str) -> Dict:
    with open(path, "r") as f:
        return json.load(f)


def dew_point_c(temp_c: float, rh: float) -> float:
    # Magnus-Formel
    if rh <= 0:
        return -100.0
    a = 17.62
    b = 243.12
    gamma = (a * temp_c) / (b + temp_c) + math.log(rh / 100.0)
    return (b * gamma) / (a - gamma)


# -----------------------------
# GPIO / Relay control
# -----------------------------
def _gpio_level_for(state_on: bool) -> int:
    """
    state_on=True means heater should be ON.
    Depending on HEATER_RELAY_INVERT:
      invert=False: ON -> HIGH, OFF -> LOW
      invert=True : ON -> LOW,  OFF -> HIGH
    """
    invert = bool(getattr(config, "HEATER_RELAY_INVERT", False))
    if invert:
        return GPIO.LOW if state_on else GPIO.HIGH
    return GPIO.HIGH if state_on else GPIO.LOW


def gpio_apply(state_on: bool) -> None:
    if GPIO is None:
        raise RuntimeError("RPi.GPIO nicht verfuegbar (kein Raspberry Pi / Paket fehlt).")

    pin = int(getattr(config, "HEATER_RELAY_PIN", 26))
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.OUT, initial=_gpio_level_for(state_on))
    # bewusst KEIN cleanup, damit Pegel bleibt


def gpio_read_current() -> Optional[bool]:
    """
    Optional: current output level lesen, wenn GPIO aktiv.
    Gibt True/False (ON/OFF) oder None falls nicht moeglich.
    """
    if GPIO is None:
        return None
    pin = int(getattr(config, "HEATER_RELAY_PIN", 26))
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.OUT)
        level = GPIO.input(pin)
        invert = bool(getattr(config, "HEATER_RELAY_INVERT", False))
        if invert:
            return True if level == GPIO.LOW else False
        return True if level == GPIO.HIGH else False
    except Exception:
        return None


# -----------------------------
# State file (min on/off)
# -----------------------------
def state_file_path() -> str:
    # AllSkyKamera/tmp/heater_state.json (relativ zum Repo)
    base = os.path.join(os.path.dirname(__file__), "..", "..", "tmp")
    base = os.path.abspath(base)
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "heater_state.json")


def load_state() -> Dict:
    p = state_file_path()
    if not os.path.isfile(p):
        return {"last_change": 0, "last_state": None, "last_reason": ""}
    try:
        with open(p, "r") as f:
            d = json.load(f)
        d.setdefault("last_change", 0)
        d.setdefault("last_state", None)
        d.setdefault("last_reason", "")
        return d
    except Exception:
        return {"last_change": 0, "last_state": None, "last_reason": ""}


def save_state(state_on: bool, reason: str) -> None:
    p = state_file_path()
    tmp = p + ".tmp"
    data = {
        "ts": iso_now_utc(),
        "last_change": int(time.time()),
        "last_state": "ON" if state_on else "OFF",
        "last_reason": reason,
    }
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, p)


# -----------------------------
# ENV reading (no merge, just consume)
# -----------------------------
def env_dir() -> str:
    # /home/pi/AllSkyKamera/tmp/env
    base = os.path.join(os.path.dirname(__file__), "..", "..", "tmp", "env")
    return os.path.abspath(base)


def pick_inside_file() -> Optional[str]:
    # Prioritaet
    order = ["bme280.json", "sht3x.json", "htu21.json", "dht22.json", "dht11.json"]
    d = env_dir()
    for fn in order:
        p = os.path.join(d, fn)
        if os.path.isfile(p):
            return p
    return None


def read_inside(max_age_sec: int) -> Optional[Tuple[float, float, float, str]]:
    """
    returns (temp_c, rh, dewpoint_c, src_file)
    """
    src = pick_inside_file()
    if not src:
        return None
    try:
        data = read_json(src)
        ts = parse_ts_utc(data.get("ts", ""))
        age = (datetime.datetime.now(datetime.timezone.utc) - ts).total_seconds()
        if age < 0 or age > max_age_sec:
            return None

        t = float(data["temp_c"])
        rh = float(data["rh"])
        if "dewpoint_c" in data and data["dewpoint_c"] is not None:
            dp = float(data["dewpoint_c"])
        else:
            dp = float(dew_point_c(t, rh))
        return (t, rh, dp, src)
    except Exception:
        return None


def read_outside_temp(max_age_sec: int) -> Optional[float]:
    p = os.path.join(env_dir(), "ds18b20.json")
    if not os.path.isfile(p):
        return None
    try:
        data = read_json(p)
        ts = parse_ts_utc(data.get("ts", ""))
        age = (datetime.datetime.now(datetime.timezone.utc) - ts).total_seconds()
        if age < 0 or age > max_age_sec:
            return None
        return float(data["temp_c"])
    except Exception:
        return None


# -----------------------------
# Decision logic
# -----------------------------
def enforce_min_times(current_on: bool, desired_on: bool, st: Dict, min_on: int, min_off: int) -> bool:
    if desired_on == current_on:
        return desired_on
    last_change = int(st.get("last_change", 0) or 0)
    age = int(time.time()) - last_change

    if current_on and (not desired_on) and age < min_on:
        return True
    if (not current_on) and desired_on and age < min_off:
        return False
    return desired_on


def decide() -> Dict:
    """
    Main public API.
    Reads env JSONs, decides heater state, applies GPIO if needed, updates state.
    Returns a dict with diagnostics (for logging/influx).
    """
    enabled = bool(getattr(config, "HEATER_ENABLED", False))
    if not enabled:
        return {"enabled": False, "action": "skip", "reason": "HEATER_ENABLED=False"}

    max_age = int(getattr(config, "ENV_MAX_AGE_SEC", 180))

    on_spread = float(getattr(config, "HEATER_ON_SPREAD_C", 2.0))
    off_spread = float(getattr(config, "HEATER_OFF_SPREAD_C", 4.0))
    min_rh = float(getattr(config, "HEATER_MIN_RH_PCT", 70.0))
    max_temp = float(getattr(config, "HEATER_MAX_TEMP_C", 18.0))
    min_on = int(getattr(config, "HEATER_MIN_ON_SEC", 180))
    min_off = int(getattr(config, "HEATER_MIN_OFF_SEC", 180))

    fail_mode = str(getattr(config, "HEATER_FAIL_MODE", "off")).lower()
    if fail_mode not in ("off", "on"):
        fail_mode = "off"

    # optional boost
    boost_enable = bool(getattr(config, "HEATER_OUTSIDE_BOOST_ENABLE", True))
    outside_cold = float(getattr(config, "HEATER_OUTSIDE_COLD_C", 0.0))
    boost_on_spread = float(getattr(config, "HEATER_BOOST_ON_SPREAD_C", 2.5))

    st = load_state()

    # Determine current state: prefer statefile, fallback GPIO read
    current = st.get("last_state")
    if current in ("ON", "OFF"):
        current_on = (current == "ON")
    else:
        g = gpio_read_current()
        current_on = bool(g) if g is not None else False

    inside = read_inside(max_age)
    t_out = read_outside_temp(max_age)

    if inside is None:
        desired_on = True if fail_mode == "on" else False
        reason = f"no_fresh_inside_sensor fail_mode={fail_mode}"
        desired_on = enforce_min_times(current_on, desired_on, st, min_on, min_off)
        return _apply_if_needed(current_on, desired_on, reason, inside=None, t_out=t_out)

    t_in, rh, dp, src = inside
    spread = t_in - dp

    eff_on_spread = on_spread
    if boost_enable and (t_out is not None) and (t_out < outside_cold):
        eff_on_spread = max(eff_on_spread, boost_on_spread)

    # decision
    if t_in >= max_temp:
        desired_on = False
        reason = f"T_in {t_in:.2f} >= max_temp {max_temp:.2f}"
    elif rh < min_rh:
        desired_on = False
        reason = f"RH {rh:.1f} < min_rh {min_rh:.1f}"
    else:
        if not current_on:
            if spread <= eff_on_spread:
                desired_on = True
                reason = f"spread {spread:.2f} <= on_spread {eff_on_spread:.2f}"
            else:
                desired_on = False
                reason = f"spread {spread:.2f} > on_spread {eff_on_spread:.2f}"
        else:
            if spread >= off_spread:
                desired_on = False
                reason = f"spread {spread:.2f} >= off_spread {off_spread:.2f}"
            else:
                desired_on = True
                reason = f"spread {spread:.2f} < off_spread {off_spread:.2f}"

    desired_on2 = enforce_min_times(current_on, desired_on, st, min_on, min_off)
    if desired_on2 != desired_on:
        reason = reason + " (min_time_hold)"
    desired_on = desired_on2

    return _apply_if_needed(current_on, desired_on, reason, inside=inside, t_out=t_out)


def _apply_if_needed(current_on: bool, desired_on: bool, reason: str, inside, t_out):
    action = "noop"
    switched = False
    err = None

    if desired_on != current_on:
        try:
            gpio_apply(desired_on)
            save_state(desired_on, reason)
            action = "switch"
            switched = True
        except Exception as e:
            err = str(e)
            action = "error"

    diag = {
        "enabled": True,
        "action": action,
        "switched": switched,
        "desired": "ON" if desired_on else "OFF",
        "current": "ON" if current_on else "OFF",
        "reason": reason,
        "t_out": float(t_out) if t_out is not None else None,
    }

    if inside is None:
        diag.update({"src": None, "t_in": None, "rh": None, "dewpoint": None, "spread": None})
    else:
        t_in, rh, dp, src = inside
        diag.update({
            "src": os.path.basename(src),
            "t_in": float(t_in),
            "rh": float(rh),
            "dewpoint": float(dp),
            "spread": float(t_in - dp),
        })

    if err:
        diag["error"] = err

    return diag
