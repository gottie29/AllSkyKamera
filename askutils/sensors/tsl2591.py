import math
import board
import busio

# -------------------------
# Adafruit-API-Kompatibilität
# -------------------------
# Neuere Bibliotheken exportieren:   TSL2591, Gain, IntegrationTime
# Ältere Bibliotheken exportieren:   TSL2591 + GAIN_* und INTEGRATIONTIME_* Konstanten
try:
    from adafruit_tsl2591 import TSL2591, Gain, IntegrationTime  # neuere API
    _API_STYLE = "enum"
except ImportError:
    import adafruit_tsl2591 as _tsl  # ältere API (Konstanten)
    TSL2591 = _tsl.TSL2591
    _API_STYLE = "const"

    # Shim-Klassen, deren Attribute auf die alten Konstanten zeigen
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
# Konfig mit Defaults
# -------------------------
TSL_GAIN_STR = getattr(config, "TSL2591_GAIN", "LOW")  # "LOW","MED","HIGH","MAX"
TSL_INTEG_MS = int(getattr(config, "TSL2591_INTEGRATION_MS", 300))  # 100..600
TSL_AUTORANGE = bool(getattr(config, "TSL2591_AUTORANGE", True))

SQM_CORR = float(getattr(config, "TSL2591_SQM_CORRECTION", 0.0))
SQM2_LIM = float(getattr(config, "TSL2591_SQM2_LIMIT", 6.0))

_gain_map_str2enum = {
    "LOW": Gain.LOW,
    "MED": Gain.MED,
    "HIGH": Gain.HIGH,
    "MAX": Gain.MAX,
}
# Werte sind hashbar → reverse Map ok
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

def _make_sensor():
    """Erstellt den Sensor und setzt Start-Settings aus der config."""
    i2c = busio.I2C(board.SCL, board.SDA)
    sensor = TSL2591(i2c)
    sensor.gain = _gain_map_str2enum.get(TSL_GAIN_STR.upper(), Gain.LOW)
    sensor.integration_time = _time_map_ms2enum.get(TSL_INTEG_MS, IntegrationTime.TIME_300MS)
    return sensor

def _autorange(sensor):
    """Einfache Auto-Range-Logik (optional)."""
    if not TSL_AUTORANGE:
        return

    counts = sensor.full_spectrum
    if counts is None:
        return

    try:
        # Dunkel → empfindlicher
        if counts < 100:
            order_g = [Gain.LOW, Gain.MED, Gain.HIGH, Gain.MAX]
            order_t = [
                IntegrationTime.TIME_100MS, IntegrationTime.TIME_200MS, IntegrationTime.TIME_300MS,
                IntegrationTime.TIME_400MS, IntegrationTime.TIME_500MS, IntegrationTime.TIME_600MS
            ]
            if sensor.gain != Gain.MAX:
                sensor.gain = order_g[min(order_g.index(sensor.gain) + 1, len(order_g) - 1)]
            elif sensor.integration_time != IntegrationTime.TIME_600MS:
                sensor.integration_time = order_t[min(order_t.index(sensor.integration_time) + 1, len(order_t) - 1)]

        # Sättigung → weniger empfindlich
        elif counts > 60000:
            order_g = [Gain.LOW, Gain.MED, Gain.HIGH, Gain.MAX]
            order_t = [
                IntegrationTime.TIME_100MS, IntegrationTime.TIME_200MS, IntegrationTime.TIME_300MS,
                IntegrationTime.TIME_400MS, IntegrationTime.TIME_500MS, IntegrationTime.TIME_600MS
            ]
            if sensor.integration_time != IntegrationTime.TIME_100MS:
                sensor.integration_time = order_t[max(order_t.index(sensor.integration_time) - 1, 0)]
            elif sensor.gain != Gain.LOW:
                sensor.gain = order_g[max(order_g.index(sensor.gain) - 1, 0)]
    except Exception:
        # Safety: nie crashen, falls die Lib intern etwas ändert
        pass

def is_connected():
    """Kurzcheck, ob Sensor ansprechbar ist und Lux liefert."""
    try:
        sensor = _make_sensor()
        _autorange(sensor)
        return sensor.lux is not None
    except Exception:
        return False

def read_tsl2591():
    """Werte + SQM berechnen und aktuelle Gain/Integration zurückgeben."""
    sensor = _make_sensor()
    _autorange(sensor)

    lux = sensor.lux
    visible = sensor.visible
    infrared = sensor.infrared
    full = sensor.full_spectrum

    lux_f = float(lux) if lux not in (None, 0) else 1e-4
    vis_f = float(visible) if visible not in (None, 0) else 1e-4

    sqm = 22.0 - 2.5 * math.log10(lux_f) + SQM_CORR
    sqm2 = 22.0 - 2.5 * math.log10(vis_f) + SQM_CORR

    if sqm2 < SQM2_LIM:
        sqm2 = 1e-4

    gain_str = _gain_map_enum2str.get(sensor.gain, "UNKNOWN")
    integ_ms = _time_map_enum2ms.get(sensor.integration_time, 0)

    return {
        "lux": round(lux_f, 2),
        "visible": int(visible) if visible is not None else 0,
        "infrared": int(infrared) if infrared is not None else 0,
        "full": int(full) if full is not None else 0,
        "sqm": round(float(sqm), 2),
        "sqm2": round(float(sqm2), 2),
        "gain": gain_str,                 # "LOW","MED","HIGH","MAX"
        "integration_ms": int(integ_ms),  # 100..600
        "autorange": bool(TSL_AUTORANGE),
    }
