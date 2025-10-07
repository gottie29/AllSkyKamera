from datetime import datetime, timedelta, timezone
import math
import os
import sys
import subprocess
from PIL import Image, ImageDraw, ImageFont


# config importieren
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from askutils import config

def get_true_solar_time(longitude, local_time):
    offset_minutes = 4 * (longitude - round(longitude / 15) * 15)
    day_of_year = local_time.timetuple().tm_yday
    b = 2 * math.pi * (day_of_year - 81) / 364
    eqtime = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)
    total_offset = offset_minutes + eqtime
    return local_time + timedelta(minutes=total_offset)

def overlay_text_on_image(image_path, text_lines, output_path):
    try:
        image = Image.open(image_path).convert("RGB")
    except FileNotFoundError:
        print(f" Bild nicht gefunden: {image_path}")
        return

    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSansMono.ttf", 32)
    except:
        font = ImageFont.load_default()

    y = 20
    for line in text_lines:
        draw.text((20, y), line, font=font, fill=(255, 255, 255))
        y += 45

    image.save(output_path)
    print(f" Bild gespeichert: {output_path}")

def bewertung_sonne_zu_sehen(image_path, threshold=240, min_percent_above=0.001):
    """
    Prüft, ob ein kleiner Bereich sehr heller Pixel im Bild vorhanden ist.
    threshold: Mindesthelligkeit (0-255)
    min_percent_above: Mindestanteil an Pixeln über threshold (z.B. 0.1 %)
    """
    try:
        img = Image.open(image_path).convert("L")
        pixels = list(img.getdata())
        total = len(pixels)
        max_pixel = max(pixels)
        above = sum(1 for p in pixels if p >= threshold)
        percent_above = above / total

        print(f"Max. Helligkeit: {max_pixel}, Pixel ≥ {threshold}: {percent_above:.4%}")

        return (max_pixel >= threshold) and (percent_above >= min_percent_above)
    except Exception as e:
        print(f" Fehler bei Bildanalyse: {e}")
        return False

def bewertung_sonne_konzentriert(image_path, threshold=240, max_blob_size=1000):
    """
    Erkennt, ob ein kleiner, konzentrierter heller Fleck (z.B. die Sonne) im Bild ist.
    threshold: Mindesthelligkeit für "hell"
    max_blob_size: Maximale Anzahl benachbarter heller Pixel für einen gültigen Punkt
    """
    try:
        img = Image.open(image_path).convert("L")
        pixels = img.load()
        width, height = img.size

        # Suche den hellsten Punkt
        max_val = -1
        max_pos = (0, 0)
        for y in range(height):
            for x in range(width):
                val = pixels[x, y]
                if val > max_val:
                    max_val = val
                    max_pos = (x, y)

        cx, cy = max_pos
        radius = 10
        bright_count = 0

        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < width and 0 <= ny < height:
                    if pixels[nx, ny] >= threshold:
                        bright_count += 1

        print(f"Max-Helligkeit: {max_val} bei {max_pos}, Helle Pixel im Umkreis: {bright_count}")

        return (max_val >= threshold) and (bright_count <= max_blob_size)

    except Exception as e:
        print(f" Fehler bei Bildbewertung: {e}")
        return False

def erzeuge_debugbild(image_path, output_path, threshold=240):
    try:
        original = Image.open(image_path).convert("RGB")
        grayscale = original.convert("L")
        draw = ImageDraw.Draw(original)

        # Finde hellste Stelle
        pixels = grayscale.load()
        width, height = original.size
        max_val = -1
        max_pos = (0, 0)

        for y in range(height):
            for x in range(width):
                val = pixels[x, y]
                if val > max_val:
                    max_val = val
                    max_pos = (x, y)

        # Markiere helle Pixel über Threshold (z.B. ab 240) als halbtransparentes Gelb
        for y in range(height):
            for x in range(width):
                if pixels[x, y] >= threshold:
                    original.putpixel((x, y), (255, 255, 0))

        # Markiere hellsten Punkt rot (vermutlich Sonne)
        draw.ellipse(
            (max_pos[0] - 10, max_pos[1] - 10, max_pos[0] + 10, max_pos[1] + 10),
            outline="red", width=3
        )

        original.save(output_path)
        print(f"Debugbild gespeichert: {output_path}")

    except Exception as e:
        print(f" Fehler beim Erzeugen des Debugbilds: {e}")

def main():
    if not getattr(config, 'ANALEMMA_ENABLED', False):
        print(" Analemma-Aufnahme ist deaktiviert (ANALEMMA_ENABLE=False)")
        return

    latitude = config.LATITUDE
    longitude = config.LONGITUDE
    width = getattr(config, 'KAMER_WIDTH', 1920)
    height = getattr(config, 'HEIGHT_HEIGHT', 1080)

    utc_now = datetime.now(timezone.utc)
    local_now = utc_now.astimezone()
    true_solar = get_true_solar_time(longitude, local_now)

    text_lines = [
        f"UTC:        {utc_now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Lokalzeit:  {local_now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Ortszeit:   {true_solar.strftime('%Y-%m-%d %H:%M:%S')}"
    ]

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    tmp_dir = os.path.join(base_dir, 'tmp')
    os.makedirs(tmp_dir, exist_ok=True)

    date_str = local_now.strftime("%Y%m%d")
    base_filename = f"analemma-{date_str}"
    temp_image = os.path.join(tmp_dir, base_filename + ".jpg")

    try:
        subprocess.run([
            'libcamera-still',
            '-o', temp_image,
            '--width', str(width),
            '--height', str(height),
            '--shutter', str(getattr(config, 'A_SHUTTER', 1000)),
            '--gain', str(getattr(config, 'A_GAIN', 1.0)),
            '--metering', 'spot',            # fest im Skript
            '--exposure', 'normal',          # fest im Skript
            '--timeout', '1000',
            '--nopreview'
        ], check=True)
        print(f"Bild aufgenommen: {temp_image}")
    except subprocess.CalledProcessError:
        print(" Fehler beim Aufnehmen des Bildes mit libcamera-still")
        return

    #overlay_text_on_image(temp_image, text_lines, temp_image)

    debug_image = os.path.join(tmp_dir, base_filename + "_debug.jpg")
    erzeuge_debugbild(temp_image, debug_image)

    #sonne_da = bewertung_sonne_zu_sehen(temp_image)
    sonne_da = bewertung_sonne_konzentriert(temp_image)
    status = "_used" if sonne_da else "_unused"
    final_image = os.path.join(tmp_dir, base_filename + status + ".jpg")

    os.rename(temp_image, final_image)
    print(f"Bild gespeichert als: {final_image}")

if __name__ == "__main__":
    main()
