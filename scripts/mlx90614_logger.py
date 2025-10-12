#!/usr/bin/python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from askutils import config
from askutils.utils.logger import log, warn, error
from askutils.utils import influx_writer
from askutils.sensors import mlx90614

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

    # Ausgabe auf Konsole
    print(f"Standort: {getattr(config, 'STANDORT_NAME', 'unbekannt')} ({getattr(config, 'KAMERA_ID', 'n/a')})")
    print(f"Umgebung: {data['ambient']:.2f} °C")
    print(f"Objekt  : {data['object']:.2f} °C")

    # Influx schreiben (Measurement: mlx90614)
    # Hinweis: Wenn du statt eines statischen Tags lieber die Kamera-ID als Host willst:
    # tags={"host": getattr(config, "KAMERA_ID", "host1")}
    try:
        influx_writer.log_metric(
            "mlx90614",
            {
                "Ambient": data["ambient"],
                "Object": data["object"],
            },
            tags={"host": "host1"}
        )
        log("MLX90614 Messwerte erfolgreich nach Influx geschrieben.")
    except Exception as e:
        warn(f"Konnte nicht nach Influx schreiben: {e}")

if __name__ == "__main__":
    main()
