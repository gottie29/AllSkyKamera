import math
import time
import board
import busio

# -------------------------
# Adafruit API compatibility
# -------------------------
try:
    from adafruit_tsl2591 import TSL2591, Gain, IntegrationTime  # newer API
    _API_STYLE = "enum"
except ImportError:
    import adafruit_tsl2591 as _tsl  # older API (constants)
    TSL2591 = _tsl.TSL2591
    _API_STYLE = "const"

    class Gain:
        LOW = _tsl.GAIN_LOW
        MED = _tsl.GAIN_MED
        HIGH = _tsl.GAIN_HIGH
        MAX = _tsl.GAIN_MAX

    class IntegrationTime:
        TIME_100MS = _tsl.INTEGRATIONTIME_100MS
        TIME_200MS = _tsl.INTEGRATIONTIME_200MS
        TIME_300MS = _tsl.INTEGRATIONTIME_300MS
        TIME_400MS = _tsl.INTEGRATIONTIME_400MS
        TIME_500MS = _tsl.INTEGRATIONTIME_500MS
        TIME_600MS = _tsl.INTEGRATIONTIME_600MS

from askutils import config

# -------------------------
# Config with defaults
# -------------------------
TSL_GAIN_STR = getattr(config, "TSL2591_GAIN", "LOW")                  # "LOW","MED","HIGH","MAX"
TSL_INTEG_MS = int(getattr(config, "TSL2591_INTEGRATION_MS", 300))     # 100..600
TSL_AUTORANGE = bool(getattr(config, "TSL2591_AUTORANGE", True))

# Legacy corrections you already use:
SQM_CORR = float(getattr(config, "TSL2591_SQM_CORRECTION", 0.0))
SQM2_LIM = float(getattr(config, "TSL2591_SQM2_LIMIT", 6.0))

# Preferred SQM from RAW CH0 (recommended)
SQM_CONST = float(getattr(config, "TSL2591_SQM_CONSTANT", 25.12))      # best current baseline for clearer skies

# Robust read defaults
READ_RETRIES = int(getattr(config, "TSL2591_READ_RETRIES", 6))
READ_RETRY_DELAY = float(getattr(config, "TSL2591_READ_RETRY_DELAY", 0.20))
MIN_CH0 = int(getattr(config, "TSL2591_MIN_CH0", 5))                   # accept low counts at night

# Night-aware autorange targets (RAW CH0)
AR_TARGET_LOW = int(getattr(config, "TSL2591_TARGET_CH0_LOW", 10))
AR_TARGET_HIGH = int(getattr(config, "TSL2591_TARGET_CH0_HIGH", 8000))
AR_MIN_VALID = int(getattr(config, "TSL2591_MIN_CH0_VALID", 5))
AR_WARMUP_READS = int(getattr(config, "TSL2591_WARMUP_READS", 2))

# -------------------------
# CloudIndex tuning (optional via config)
# -------------------------
# Baseline "clear-ish" SQM_RAW for your site (tune later if desired)
CLOUD_CLEAR_SQM = float(getattr(config, "TSL2591_CLOUD_CLEAR_SQM", 21.0))

# IR ratio thresholds (CH1/CH0)
CLOUD_IR_T1 = float(getattr(config, "TSL2591_CLOUD_IR_T1", 0.45))
CLOUD_IR_T2 = float(getattr(config, "TSL2591_CLOUD_IR_T2", 0.55))
CLOUD_IR_T3 = float(getattr(config, "TSL2591_CLOUD_IR_T3", 0.65))

# Brightening thresholds (delta = sqm_raw - clear_sqm; negative delta => brighter sky)
CLOUD_D1 = float(getattr(config, "TSL2591_CLOUD_DELTA1", -0.30))
CLOUD_D2 = float(getattr(config, "TSL2591_CLOUD_DELTA2", -0.70))
CLOUD_D3 = float(getattr(config, "TSL2591_CLOUD_DELTA3", -1.20))

_gain_map_str2enum = {
    "LOW": Gain.LOW,
    "MED": Gain.MED,
    "HIGH": Gain.HIGH,
    "MAX": Gain.MAX,
}
_gain_map_enum2str = {v: k for k, v in _gain_map_str2enum.items()}

_time_map_ms2enum = {
    100: IntegrationTime.TIME_100MS,
    200: IntegrationTime.TIME_200MS,
    300: IntegrationTime.TIME_300MS,
    400: IntegrationTime.TIME_400MS,
    500: IntegrationTime.TIME_500MS,
    600: IntegrationTime.TIME_600MS,
}
_time_map_enum2ms = {v: k for k, v in _time_map_ms2enum.items()}


# -------------------------
# Internal helpers (robust)
# -------------------------
_i2c = None
_sensor = None


def _settle_for_integration(ms: int) -> None:
    time.sleep(ms / 1000.0 + 0.08)


def _make_or_get_sensor():
    """Create sensor once and reuse it; re-create on failure."""
    global _i2c, _sensor
    try:
        if _i2c is None:
            _i2c = busio.I2C(board.SCL, board.SDA)
        if _sensor is None:
            _sensor = TSL2591(_i2c)

        _sensor.gain = _gain_map_str2enum.get(TSL_GAIN_STR.upper(), Gain.LOW)
        _sensor.integration_time = _time_map_ms2enum.get(TSL_INTEG_MS, IntegrationTime.TIME_300MS)
        return _sensor
    except Exception:
        _i2c = None
        _sensor = None
        _i2c = busio.I2C(board.SCL, board.SDA)
        _sensor = TSL2591(_i2c)
        _sensor.gain = _gain_map_str2enum.get(TSL_GAIN_STR.upper(), Gain.LOW)
        _sensor.integration_time = _time_map_ms2enum.get(TSL_INTEG_MS, IntegrationTime.TIME_300MS)
        return _sensor


def _read_raw(sensor):
    """Return raw tuple (ch0, ch1) or (None, None)."""
    try:
        raw = sensor.raw_luminosity
        if isinstance(raw, tuple) and len(raw) >= 2:
            return int(raw[0]), int(raw[1])
    except Exception:
        pass
    return None, None


def _warmup(sensor, integ_ms: int, reads: int) -> None:
    for _ in range(max(0, reads)):
        _settle_for_integration(integ_ms)
        _ = _read_raw(sensor)


def _read_valid_raw(sensor, integ_ms: int):
    """
    Robust read:
    - Ignore 0/0
    - Ignore too-low CH0 if MIN_CH0 > 0
    Returns (ch0, ch1, note) where note: 'ok', 'zero_read', 'too_low', 'raw_missing'
    """
    last_note = "invalid"
    for _ in range(max(1, READ_RETRIES)):
        ch0, ch1 = _read_raw(sensor)
        if ch0 is None:
            return None, None, "raw_missing"

        if ch0 == 0 and ch1 == 0:
            last_note = "zero_read"
            time.sleep(READ_RETRY_DELAY)
            _settle_for_integration(integ_ms)
            continue

        if MIN_CH0 > 0 and ch0 < MIN_CH0:
            last_note = "too_low"
            time.sleep(READ_RETRY_DELAY)
            _settle_for_integration(integ_ms)
            continue

        return ch0, ch1, "ok"

    return None, None, last_note


def _autorange_night(sensor):
    """
    Night-aware autorange using RAW CH0 counts:
    - Must produce VALID reads (not 0/0, CH0 >= AR_MIN_VALID)
    - Prefer CH0 within [AR_TARGET_LOW .. AR_TARGET_HIGH]
    - Otherwise choose best SNR below target_high (maximize CH0)
    """
    if not TSL_AUTORANGE:
        return "fixed"

    gain_factors = {"LOW": 1, "MED": 25, "HIGH": 428, "MAX": 9876}
    gains = ["LOW", "MED", "HIGH", "MAX"]
    expos = [100, 200, 300, 400, 500, 600]

    combos = []
    for g in gains:
        for e in expos:
            combos.append((gain_factors[g] * e, g, e))

    combos.sort(key=lambda x: x[0], reverse=True)  # high sensitivity first

    best = None
    best_score = None

    for _, g, e in combos:
        try:
            sensor.gain = _gain_map_str2enum[g]
            sensor.integration_time = _time_map_ms2enum[e]
        except Exception:
            continue

        _warmup(sensor, e, AR_WARMUP_READS)
        _settle_for_integration(e)
        ch0, ch1 = _read_raw(sensor)

        if ch0 is None:
            return "autorange_raw_missing"

        if ch0 == 0 and ch1 == 0:
            continue

        if AR_MIN_VALID > 0 and ch0 < AR_MIN_VALID:
            continue

        if AR_TARGET_LOW <= ch0 <= AR_TARGET_HIGH:
            return "autorange_ok"

        if ch0 <= AR_TARGET_HIGH:
            score = ch0
        else:
            score = AR_TARGET_HIGH - (ch0 - AR_TARGET_HIGH)

        if best_score is None or score > best_score:
            best_score = score
            best = (g, e)

    if best is not None:
        g, e = best
        sensor.gain = _gain_map_str2enum[g]
        sensor.integration_time = _time_map_ms2enum[e]
        _warmup(sensor, e, AR_WARMUP_READS)
        return "autorange_best"

    sensor.gain = Gain.MAX
    sensor.integration_time = IntegrationTime.TIME_600MS
    _warmup(sensor, 600, AR_WARMUP_READS)
    return "autorange_fallback"


# -------------------------
# CloudIndex computation
# -------------------------
def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _norm(x: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return _clamp01((x - lo) / (hi - lo))


def compute_cloud_index(sqm_raw: float, ir_ratio: float, clear_sqm: float) -> tuple:
    """
    Returns: (cloud_score_0_1, cloud_index_0_3)
    Heuristic:
      - score_ir from IRRatio (higher -> more likely clouds/haze)
      - score_bright from brightness delta vs clear baseline (brighter than clear -> more clouds, typical in urban areas)
      - final score = max(score_ir, score_bright)
    """
    if sqm_raw is None or sqm_raw <= 0:
        sqm_raw = float("nan")
    if ir_ratio is None or ir_ratio < 0:
        ir_ratio = float("nan")

    # IR component: map across [T1..T3] -> 0..1
    if math.isfinite(ir_ratio):
        score_ir = _norm(ir_ratio, CLOUD_IR_T1, CLOUD_IR_T3)
    else:
        score_ir = 0.0

    # Brightness component
    # delta = sqm_raw - clear_sqm (negative => brighter sky)
    if math.isfinite(sqm_raw):
        delta = float(sqm_raw) - float(clear_sqm)
        # more negative => more clouds (in light-polluted conditions)
        # map -delta across [-D1 .. -D3]
        score_bright = _norm(-delta, -CLOUD_D1, -CLOUD_D3)
    else:
        score_bright = 0.0

    cloud_score = max(score_ir, score_bright)

    if cloud_score < 0.25:
        cloud_index = 0
    elif cloud_score < 0.50:
        cloud_index = 1
    elif cloud_score < 0.75:
        cloud_index = 2
    else:
        cloud_index = 3

    return round(cloud_score, 3), int(cloud_index)


# -------------------------
# Public API
# -------------------------
def is_connected():
    """Quick check if sensor responds with RAW counts at least once."""
    try:
        sensor = _make_or_get_sensor()
        _ = _autorange_night(sensor)
        integ_ms = _time_map_enum2ms.get(sensor.integration_time, 300)
        ch0, ch1, note = _read_valid_raw(sensor, integ_ms)
        return ch0 is not None
    except Exception:
        return False


def read_tsl2591():
    """
    Read sensor values and return:
    - RAW channels (ch0/ch1)
    - Ratio CH1/CH0
    - SQM from RAW CH0 (preferred)
    - Legacy SQM from lux/visible (kept for compatibility)
    - CloudScore (0..1) and CloudIndex (0..3)
    """
    sensor = _make_or_get_sensor()
    autorange_reason = _autorange_night(sensor)

    integ_ms = _time_map_enum2ms.get(sensor.integration_time, 0)
    if integ_ms <= 0:
        integ_ms = 300

    _settle_for_integration(integ_ms)

    ch0, ch1, note = _read_valid_raw(sensor, integ_ms)

    # Informational values (may be 0/weird at night)
    try:
        lux = sensor.lux
    except Exception:
        lux = None
    try:
        visible = sensor.visible
    except Exception:
        visible = None
    try:
        infrared = sensor.infrared
    except Exception:
        infrared = None
    try:
        full = sensor.full_spectrum
    except Exception:
        full = None

    lux_f = float(lux) if lux not in (None, 0) else 1e-4
    vis_f = float(visible) if visible not in (None, 0) else 1e-4

    # Legacy SQM (lux/visible)
    sqm_lux = 22.0 - 2.5 * math.log10(lux_f) + SQM_CORR
    sqm_vis = 22.0 - 2.5 * math.log10(vis_f) + SQM_CORR
    if sqm_vis < SQM2_LIM:
        sqm_vis = 1e-4

    # Preferred SQM from RAW CH0
    if ch0 is not None and ch0 > 0:
        sqm_raw = SQM_CONST - 2.5 * math.log10(float(ch0)) + SQM_CORR
    else:
        sqm_raw = float("nan")

    # IR ratio
    if ch0 is not None and ch0 > 0 and ch1 is not None and ch1 >= 0:
        ir_ratio = float(ch1) / float(ch0)
    else:
        ir_ratio = float("nan")

    # Cloud metrics
    cloud_score, cloud_index = compute_cloud_index(
        sqm_raw=sqm_raw if math.isfinite(sqm_raw) else float("nan"),
        ir_ratio=ir_ratio if math.isfinite(ir_ratio) else float("nan"),
        clear_sqm=CLOUD_CLEAR_SQM,
    )

    gain_str = _gain_map_enum2str.get(sensor.gain, "UNKNOWN")

    return {
        "lux": round(lux_f, 4),
        "visible": int(visible) if visible is not None else 0,
        "infrared": int(infrared) if infrared is not None else 0,
        "full": int(full) if full is not None else 0,

        # RAW
        "ch0": int(ch0) if ch0 is not None else 0,
        "ch1": int(ch1) if ch1 is not None else 0,
        "ir_ratio": round(ir_ratio, 4) if math.isfinite(ir_ratio) else -1.0,
        "read_note": note,

        # SQM
        "sqm_raw": round(float(sqm_raw), 3) if math.isfinite(sqm_raw) else -1.0,
        "sqm": round(float(sqm_lux), 3),
        "sqm2": round(float(sqm_vis), 3),
        "sqm_const": float(SQM_CONST),

        # Cloud
        "cloud_score": float(cloud_score),   # 0..1
        "cloud_index": int(cloud_index),     # 0..3 (0=clear ... 3=overcast)

        # Settings
        "gain": gain_str,
        "integration_ms": int(integ_ms),
        "autorange": bool(TSL_AUTORANGE),
        "autorange_reason": autorange_reason,
    }
