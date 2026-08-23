#!/usr/bin/env python3

import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


TJ_SETTINGS = "/home/pi/allsky/config/settings.json"
TJ_OVERLAY_DIRS = [
    "/home/pi/allsky/config/overlay/myTemplates",
    "/home/pi/allsky/config/overlay/config",
]

OUTPUT_DIR = "/home/pi/AllSkyKamera/tmp/growing_startrail_mask"

DEFAULT_FONT_SIZE = 48
PADDING = 12


def log(msg):
    print(f"[TJ-MASK] {msg}", flush=True)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_overlay_file(settings):
    overlay_name = settings.get("nighttimeoverlay")

    if not overlay_name:
        raise RuntimeError("In settings.json wurde kein 'nighttimeoverlay' gefunden.")

    log(f"Aktives Nacht-Overlay: {overlay_name}")

    for directory in TJ_OVERLAY_DIRS:
        candidate = os.path.join(directory, overlay_name)
        if os.path.isfile(candidate):
            return candidate

    raise FileNotFoundError(
        f"Overlay-Datei '{overlay_name}' wurde in keinem bekannten Verzeichnis gefunden."
    )


def get_resolution(overlay):
    metadata = overlay.get("metadata", {})

    width = int(metadata.get("cameraresolutionwidth", 0))
    height = int(metadata.get("cameraresolutionheight", 0))

    if width <= 0 or height <= 0:
        raise RuntimeError(
            "Kameraauflösung fehlt oder ist ungültig in overlay.metadata."
        )

    return width, height


def resolve_overlay_image(image_name):
    candidates = [
        "/home/pi/allsky/config/overlay/images",
        "/home/pi/allsky/config/overlay/extra",
        "/home/pi/allsky/config/overlay/myTemplates",
    ]

    for directory in candidates:
        path = os.path.join(directory, image_name)
        if os.path.isfile(path):
            return path

    return None


def estimate_text_box(draw, field, overlay_settings):
    label = str(field.get("label", ""))

    fontsize = int(
        field.get(
            "fontsize",
            overlay_settings.get("defaultfontsize", DEFAULT_FONT_SIZE)
        )
    )

    tlx = int(float(field.get("tlx", field.get("x", 0))))
    tly = int(float(field.get("tly", field.get("y", 0))))

    # Variablen durch großzügige Beispielwerte ersetzen.
    replacements = {
        "${DATE}": "31.12.2026",
        "${TIME}": "23:59:59",
        "${sEXPOSURE}": "60000",
        "${GAIN}": "12.000",
        "${MEAN}": "0.999",
        "${TEMPERATURE_C}": "-99.9",
        "${BME280_TEMP}": "-99.99",
        "${BME280_HUM}": "100.00",
        "${BME280_PRESS}": "1099.99",
        "${DS18B20_TEMP}": "-99.99",
        "${MOON_ILLUMINATION}": "100.0",
        "${MOON_ELEVATION}": "-90.00°",
        "${MOON_SYMBOL}": "W",
        "${SUN_SUNRISE}": "23:59",
        "${SUN_SUNSET}": "23:59",
        "${CAMERA_TYPE}": "RaspberryPi",
        "${CAMERA_MODEL}": "RPi HQ Camera",
    }

    sample = label
    for key, value in replacements.items():
        sample = sample.replace(key, value)

    # Falls unbekannte Variablen übrig bleiben, breit genug ersetzen.
    while "${" in sample:
        start = sample.find("${")
        end = sample.find("}", start)

        if end == -1:
            break

        sample = sample[:start] + "XXXXXXXXXX" + sample[end + 1:]

    # PIL-Defaultfont ist für echte Größenberechnung ungeeignet.
    # Daher zunächst robuste Näherung anhand der Schriftgröße.
    char_width = fontsize * 0.68
    width = max(fontsize, int(len(sample) * char_width))
    height = int(fontsize * 1.45)

    x1 = max(0, tlx - PADDING)
    y1 = max(0, tly - PADDING)
    x2 = tlx + width + PADDING
    y2 = tly + height + PADDING

    return x1, y1, x2, y2


def image_box(item):
    image_name = item.get("image")
    if not image_name:
        return None

    image_path = resolve_overlay_image(image_name)

    if image_path is None:
        log(f"WARNUNG: Overlay-Bild nicht gefunden: {image_name}")
        return None

    try:
        with Image.open(image_path) as img:
            iw, ih = img.size
    except Exception as e:
        log(f"WARNUNG: Bild konnte nicht gelesen werden: {image_path}: {e}")
        return None

    scale = float(item.get("scale", 1.0))

    iw = int(iw * scale)
    ih = int(ih * scale)

    # TJ liefert tlx/tly offenbar als Top-Left des Elements.
    tlx = int(float(item.get("tlx", item.get("x", 0))))
    tly = int(float(item.get("tly", item.get("y", 0))))

    x1 = max(0, tlx - PADDING)
    y1 = max(0, tly - PADDING)
    x2 = tlx + iw + PADDING
    y2 = tly + ih + PADDING

    return x1, y1, x2, y2


def create_mask(overlay):
    width, height = get_resolution(overlay)

    log(f"Maskenauflösung: {width} x {height}")

    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)

    overlay_settings = overlay.get("settings", {})

    field_count = 0
    for field in overlay.get("fields", []):
        box = estimate_text_box(draw, field, overlay_settings)

        x1, y1, x2, y2 = box

        x2 = min(width, x2)
        y2 = min(height, y2)

        draw.rectangle((x1, y1, x2, y2), fill=255)

        log(
            f"FIELD {field.get('id')} "
            f"{field.get('label')} -> "
            f"{x1},{y1} bis {x2},{y2}"
        )

        field_count += 1

    image_count = 0
    for item in overlay.get("images", []):
        box = image_box(item)

        if box is None:
            continue

        x1, y1, x2, y2 = box

        x2 = min(width, x2)
        y2 = min(height, y2)

        draw.rectangle((x1, y1, x2, y2), fill=255)

        log(
            f"IMAGE {item.get('id')} "
            f"{item.get('image')} -> "
            f"{x1},{y1} bis {x2},{y2}"
        )

        image_count += 1

    log(f"Textfelder maskiert: {field_count}")
    log(f"Bilder maskiert: {image_count}")

    return mask


def create_preview(mask, source_image, output_path):
    with Image.open(source_image).convert("RGB") as base:
        if base.size != mask.size:
            log(
                f"Preview-Bild hat Größe {base.size}, "
                f"Maske hat {mask.size}. "
                f"Maske wird für Preview skaliert."
            )
            preview_mask = mask.resize(base.size, Image.Resampling.NEAREST)
        else:
            preview_mask = mask

        overlay = Image.new("RGB", base.size, (255, 0, 0))

        result = Image.composite(
            Image.blend(base, overlay, 0.45),
            base,
            preview_mask
        )

        result.save(output_path, quality=92)


def main():
    source_image = None

    if len(sys.argv) > 2:
        print(
            "Verwendung:\n"
            "  python3 scripts/generate_tj_overlay_mask.py\n"
            "  python3 scripts/generate_tj_overlay_mask.py /pfad/zum/nachtbild.jpg"
        )
        sys.exit(1)

    if len(sys.argv) == 2:
        source_image = sys.argv[1]

        if not os.path.isfile(source_image):
            raise FileNotFoundError(
                f"Preview-Bild wurde nicht gefunden: {source_image}"
            )

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    log(f"Lese TJ-Settings: {TJ_SETTINGS}")
    settings = load_json(TJ_SETTINGS)

    overlay_path = find_overlay_file(settings)

    log(f"Lese Overlay: {overlay_path}")
    overlay = load_json(overlay_path)

    mask = create_mask(overlay)

    mask_path = os.path.join(OUTPUT_DIR, "ASK002-tj-overlay-mask.png")
    mask.save(mask_path)

    log(f"Maske gespeichert: {mask_path}")

    if source_image:
        preview_path = os.path.join(
            OUTPUT_DIR,
            "ASK002-tj-overlay-mask-preview.jpg"
        )

        create_preview(mask, source_image, preview_path)

        log(f"Preview gespeichert: {preview_path}")

    log("Fertig.")


if __name__ == "__main__":
    main()
