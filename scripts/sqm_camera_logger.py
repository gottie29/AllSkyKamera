# File: scripts/sqm_camera_logger.py
#!/usr/bin/env python3

"""
Logger für fortlaufende SQM-Messungen:
liest image.jpg + metadata.txt, berechnet μ und schreibt in InfluxDB.
"""

import os
from askutils.utils.sqm import measure_sky_brightness
from askutils import config
from askutils.utils.logger import log, error
from askutils.utils.influx_writer import log_metric

def main():
    image_path = os.path.join(config.ALLSKY_PATH, config.IMAGE_PATH, 'image.jpg')
    meta_path  = os.path.join(config.ALLSKY_PATH, config.IMAGE_PATH, 'metadata.txt')

    if not os.path.isfile(image_path) or not os.path.isfile(meta_path):
        error(f"Datei fehlt: {image_path} oder {meta_path}")
        return

    try:
        mu, gain, exptime = measure_sky_brightness(image_path, meta_path)
        # InfluxDB schreiben
        log_metric('sqm', {'mag': mu, 'gain': gain, 'exptime': exptime},
                   tags={'kamera': config.KAMERA_ID})
        log(f"SQM: μ={mu:.2f}, gain={gain:.3f}, exp={exptime:.6f}s")
    except Exception as e:
        error(f"SQM-Messung fehlgeschlagen: {e}")

if __name__ == '__main__':
    main()
