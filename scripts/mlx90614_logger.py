#!/usr/bin/python3
import sys
import os
import math

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from askutils import config
from askutils.utils.logger import log, warn, error
from askutils.utils import influx_writer
from askutils.sensors import mlx90614


# ------------------------------------------------------------
# Hilfsfunktionen für CloudWatcher-Modell
# ------------------------------------------------------------

def sgn(x: float) -> int:
    """Vorzeichenfunktion: -1, 0 oder +1."""
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


def compute_tsky_cloudwatcher(
    Ts: float,
    Ta: float,
    K1: float = 100.0,
    K2: float = 0.0,
    K3: float = 0.0,
    K4: float = 0.0,
    K5: float = 0.0,
    K6: float = 0.0,
    K7: float = 0.0,
) -> float:
    """
    Berechnet die korrigierte Himmels-Temperatur Tsky nach dem
    CloudWatcher-Modell.

    Ts : MLX90614-Objekttemperatur (Himmel) in °C
    Ta : Ambient-Temperatur in °C (z.B. BME280 oder MLX-Ambient)
    K1..K7 : CloudWatcher-Koeffizienten (aus config.py)

    Spezialfälle lt. Manual:
      - K1=100, K2..K7=0  -> Tsky = Ts - Ta
      - alle K = 0        -> Tsky = Ts (Roh-IR)
    """

    # Zentrumstemperatur aus K2
    T0 = K2 / 10.0
    d = abs(T0 - Ta)

    # --- T67-Term (kaltes Wetter) ---
    if K6 == 0.0:
        # Wenn K6 = 0, fällt T67 vollständig weg
        T67 = 0.0
    else:
        if d < 1.0:
            # |T0 - Ta| < 1
            T67 = sgn(K6) * sgn(Ta - T0) * d
        else:
            # |T0 - Ta| >= 1
            # log(d) / log(10) entspricht log10(d)
            T67 = (K6 / 10.0) * sgn(Ta - T0) * (math.log(d) / math.log(10.0) + K7 / 100.0)

    # --- Hauptterm Td ---
    term1 = (K1 / 100.0) * (Ta - T0)
    term2 = (K3 / 100.0) * (math.exp((K4 / 1000.0) * Ta) ** (K5 / 100.0))

    Td = term1 + term2 + T67

    # --- korrigierte Sky-Temperatur ---
    Tsky = Ts - Td
    return Tsky


def classify_cloudiness(Tsky: float) -> int:
    """
    Bewölkungsgrad als Integer.

    Achtung: Die Schwellenwerte sind erstmal heurisch und
    sollten mit echten Daten kalibriert werden!

    Vorschlag:
      0 = klar
      1 = leicht bewölkt
      2 = stark bewölkt
      3 = bedeckt
    """
    # Diese Grenzen sind nur ein Startpunkt!
    if Tsky <= -25.0:
        return 0  # klar
    elif Tsky <= -18.0:
        return 1  # leicht bewölkt
    elif Tsky <= -12.0:
        return 2  # stark bewölkt
    else:
        return 3  # bedeckt


def main():
    if not getattr(config, "MLX90614_ENABLED", False):
        print("MLX90614 ist deaktiviert. Test wird übersprungen.")
        return

    if not mlx90614.is_connected():
        error("MLX90614 ist nicht verbunden oder liefert keine plausiblen Werte.")
        return

    try:
        data = mlx90614.read_mlx90614()
    except Exception as e:
        error(f"Fehler beim Auslesen des MLX90614: {e}")
        return

    ambient = data["ambient"]
    obj = data["object"]

    # --------------------------------------------------------
    # CloudWatcher-Koeffizienten aus config.py lesen
    # Falls nicht vorhanden -> Defaults:
    #   K1=100, K2..K7=0  => entspricht Tsky = Ts - Ta
    # --------------------------------------------------------
    K1 = getattr(config, "MLX_CLOUD_K1", 100.0)
    K2 = getattr(config, "MLX_CLOUD_K2", 0.0)
    K3 = getattr(config, "MLX_CLOUD_K3", 0.0)
    K4 = getattr(config, "MLX_CLOUD_K4", 0.0)
    K5 = getattr(config, "MLX_CLOUD_K5", 0.0)
    K6 = getattr(config, "MLX_CLOUD_K6", 0.0)
    K7 = getattr(config, "MLX_CLOUD_K7", 0.0)

    # einfache Differenz (dein bisheriger Ansatz)
    delta_simple = obj - ambient

    # korrigierte Himmels-Temperatur nach CloudWatcher
    Tsky = compute_tsky_cloudwatcher(
        Ts=obj,
        Ta=ambient,
        K1=K1,
        K2=K2,
        K3=K3,
        K4=K4,
        K5=K5,
        K6=K6,
        K7=K7,
    )

    # Bewölkungsgrad als Integer
    cloud_state = classify_cloudiness(Tsky)

    # Ausgabe auf Konsole
    print(f"Standort       : {getattr(config, 'STANDORT_NAME', 'unbekannt')} ({getattr(config, 'KAMERA_ID', 'n/a')})")
    print(f"Umgebung (Ta)  : {ambient:.2f} °C")
    print(f"Objekt   (Ts)  : {obj:.2f} °C")
    print(f"ΔT (Ts - Ta)   : {delta_simple:.2f} °C")
    print(f"Tsky korrigiert: {Tsky:.2f} °C")
    print(f"Bewölkung (int): {cloud_state}")

    # Influx schreiben (Measurement: mlx90614)
    # Felder:
    #   - Ambient          (Ta)
    #   - Object           (Ts)
    #   - DeltaSimple      (Ts - Ta)
    #   - Tsky             (korrigierte Sky-Temperatur)
    #   - CloudState       (Integer-Bewölkungsgrad)
    try:
        influx_writer.log_metric(
            "mlx90614",
            {
                "Ambient": ambient,
                "Object": obj,
                "DeltaSimple": delta_simple,
                "Tsky": Tsky,
                "CloudState": cloud_state,  # INT
            },
            tags={"host": getattr(config, "KAMERA_ID", "host1")}
        )
        log("MLX90614 Messwerte erfolgreich nach Influx geschrieben.")
    except Exception as e:
        warn(f"Konnte nicht nach Influx schreiben: {e}")


if __name__ == "__main__":
    main()
