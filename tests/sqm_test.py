#!/usr/bin/env python3
# File: sqm_test.py
# Location: /home/pi/allsky/tests

import os
import numpy as np
from PIL import Image
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

# Optional: install matplotlib if missing
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
except ImportError:
    print("Fehler: matplotlib nicht installiert.\nInstalliere mit: sudo apt-get install python3-matplotlib oder pip3 install matplotlib")
    exit(1)
# Optional: install astral if missing
try:
    from astral import LocationInfo
    from astral.sun import sun, dawn, dusk
except ImportError:
    print("Fehler: astral nicht installiert.\nInstalliere mit: pip3 install astral")
    exit(1)

# Camera parameters for Raspberry Pi HQ (IMX477, 1/1.8" lens)
pix_size_mm = 0.00155  # mm (1.55 µm pixel size)
focal_mm = 1.85        # mm focal length
ZP = 6.0              # Zero point (mag)
patch_size = 100       # pixels around image center

# Location for sun calculations
LATITUDE = 52.486834
LONGITUDE = 13.475197
TIMEZONE = 'Europe/Berlin'

# Paths (dynamic per day)
script_dir = os.path.dirname(__file__)
# Use today's date in filename: YYYYMMDD
now = datetime.now(ZoneInfo(TIMEZONE))
date0 = now.date()
date1 = date0 + timedelta(days=1)
date0_str = date0.strftime('%Y%m%d')
# Data and plot filenames include today's date
data_file = os.path.join(script_dir, f'brightness_history_{date0_str}.csv')
plot_file = os.path.join(script_dir, f'sky_brightness_{date0_str}.png')


def compute_sky_brightness(patch, gain, exptime, pix_size_mm, focal_mm, ZP):
    """
    Compute sky brightness in mag/arcsec^2 from a pixel patch.
    """
    C_sky = np.median(patch)
    F_inst = C_sky * gain / exptime
    A_pix = (pix_size_mm / focal_mm * 206265.0) ** 2
    mu = ZP - 2.5 * np.log10(F_inst / A_pix)
    return mu


def read_metadata(meta_path):
    """
    Read metadata.txt with key=value lines.
    Returns dict of values.
    """
    meta = {}
    with open(meta_path, 'r') as f:
        for line in f:
            if '=' not in line:
                continue
            key, val = line.strip().split('=', 1)
            meta[key] = val.strip().strip('[]')
    return meta


if __name__ == '__main__':
    # Paths to dynamic image and metadata
    image_path = '/home/pi/allsky/tmp/image.jpg'
    meta_path = '/home/pi/allsky/tmp/metadata.txt'

    # Verify files exist
    if not os.path.isfile(image_path) or not os.path.isfile(meta_path):
        print(f"Fehler: {image_path} oder {meta_path} nicht gefunden.")
        exit(1)

    # Read metadata
    meta = read_metadata(meta_path)
    exp_us = float(meta.get('ExposureTime', 0))
    exptime = exp_us / 1e6
    analogue = float(meta.get('AnalogueGain', 1.0))
    digital = float(meta.get('DigitalGain', 1.0))
    gain = analogue * digital

    # Extract zenith patch
    img = Image.open(image_path).convert('L')
    data = np.array(img, dtype=float)
    h, w = data.shape
    cx, cy = w // 2, h // 2
    half = patch_size // 2
    patch = data[cy-half:cy+half, cx-half:cx+half]

    # Compute brightness
    mu = compute_sky_brightness(patch, gain, exptime, pix_size_mm, focal_mm, ZP)
    ts = now.isoformat(sep=' ', timespec='seconds')

    # Append to daily CSV
    header = 'timestamp,mu_mag_arcsec2,gain,exptime'
    if not os.path.isfile(data_file):
        with open(data_file, 'w') as f:
            f.write(header + '\n')
    with open(data_file, 'a') as f:
        f.write(f"{ts},{mu:.2f},{gain:.3f},{exptime:.6f}\n")

    print(f"{ts} -> μ = {mu:.2f} mag/arcsec², Gain={gain:.3f}, Exptime={exptime:.6f}s gespeichert in {data_file}")

    # Load history for today
    times, mus = [], []
    with open(data_file) as f:
        next(f)
        for line in f:
            parts = line.strip().split(',')
            try:
                dt = datetime.fromisoformat(parts[0])
                times.append(dt)
                mus.append(float(parts[1]))
            except Exception:
                continue

    # Compute sun and twilight times for today
    loc = LocationInfo('', '', TIMEZONE, LATITUDE, LONGITUDE)
    sun_times = sun(loc.observer, date=date0, tzinfo=ZoneInfo(TIMEZONE))
    civil_dawn = sun_times.get('dawn')
    sunrise = sun_times.get('sunrise')
    sunset = sun_times.get('sunset')
    civil_dusk = sun_times.get('dusk')
    # Nautical
    try:
        nautical_dawn = dawn(loc.observer, date=date0, tzinfo=ZoneInfo(TIMEZONE), depression=12)
        nautical_dusk = dusk(loc.observer, date=date0, tzinfo=ZoneInfo(TIMEZONE), depression=12)
    except ValueError:
        nautical_dawn = nautical_dusk = None
    # Astronomical
    try:
        astro_dawn = dawn(loc.observer, date=date0, tzinfo=ZoneInfo(TIMEZONE), depression=18)
        astro_dusk = dusk(loc.observer, date=date0, tzinfo=ZoneInfo(TIMEZONE), depression=18)
    except ValueError:
        astro_dawn = astro_dusk = None

    # Define events with German labels and colors
    events = [
        (civil_dawn, 'Bürgerliche Daemmerung Beginn'),
        (sunrise, 'Sonnenaufgang'),
        (sunset, 'Sonnenuntergang'),
        (civil_dusk, 'Bürgerliche Daemmerung Ende'),
        (nautical_dawn, 'Nautische Daemmerung Beginn'),
        (nautical_dusk, 'Nautische Daemmerung Ende'),
        (astro_dawn, 'Astronomische Daemmerung Beginn'),
        (astro_dusk, 'Astronomische Daemmerung Ende')
    ]
    color_map = {
        'Bürgerliche Daemmerung Beginn': 'gold',
        'Sonnenaufgang': 'yellowgreen',
        'Sonnenuntergang': 'orangered',
        'Bürgerliche Daemmerung Ende': 'goldenrod',
        'Nautische Daemmerung Beginn': 'deepskyblue',
        'Nautische Daemmerung Ende': 'dodgerblue',
        'Astronomische Daemmerung Beginn': 'midnightblue',
        'Astronomische Daemmerung Ende': 'navy'
    }

    # Determine plot window: heute 12:00 bis morgen 12:00 with timezone
    tz = ZoneInfo(TIMEZONE)
    start_time = datetime.combine(date0, time(12, 0), tzinfo=tz)
    end_time = datetime.combine(date1, time(12, 0), tzinfo=tz)

    # Plot
    plt.figure(figsize=(12, 6))
    plt.plot(times, mus, marker='o', linestyle='-', label='Himmelshelligkeit')
    # Bortle thresholds
    plt.axhline(19.1, linewidth=1, linestyle='--', label='Bortle 5 (19,1)')
    plt.axhline(18.0, linewidth=1, linestyle='--', label='Bortle 6/7 (18,0)')

    # Draw event lines
    for t, label in events:
        if t and start_time <= t <= end_time:
            plt.axvline(t, linestyle=':', color=color_map[label], label=label)

    # Title with date range
    date0_label = date0.isoformat()
    date1_label = date1.isoformat()
    plt.title(f'Himmelshelligkeit {date0_label} bis {date1_label}', fontsize='small')
    plt.xlabel('Zeit', fontsize='small')
    plt.ylabel('mag/arcsec²', fontsize='small')
    plt.grid(True)
    plt.xlim(start_time, end_time)
    plt.legend(loc='upper right', ncol=2, fontsize='small')
    # Format ticks smaller
    plt.gca().tick_params(axis='both', labelsize='small')
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.gcf().autofmt_xdate()
    plt.tight_layout()
    plt.savefig(plot_file, dpi=150)
    print(f"Plot aktualisiert: {plot_file}")
    plt.show()
