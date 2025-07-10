# File: askutils/utils/sqm.py
# Core functions for Sky Quality Meter (SQM) processing

import os
import numpy as np
from PIL import Image

from askutils import config

def read_metadata(meta_path):
    """
    Read key=value pairs from metadata.txt and return as dict.
    """
    meta = {}
    with open(meta_path, 'r', encoding='utf-8') as f:
        for line in f:
            if '=' not in line:
                continue
            key, val = line.strip().split('=', 1)
            meta[key] = val.strip().strip('[]')
    return meta

def get_zenith_patch(image_path, patch_size=None):
    """
    Load image, convert to grayscale, and extract a square patch around the center.
    Returns numpy array of patch.
    """
    patch_size = patch_size or config.SQM_PATCH_SIZE
    img = Image.open(image_path).convert('L')
    data = np.array(img, dtype=float)
    h, w = data.shape
    cx, cy = w // 2, h // 2
    half = patch_size // 2
    return data[cy-half:cy+half, cx-half:cx+half]

def compute_sky_brightness(patch, gain, exptime):
    """
    Compute sky brightness (mu) in mag/arcsec^2 from a pixel patch.
    Uses camera parameters from config: PIX_SIZE_MM, FOCAL_MM, ZP.
    """
    C_sky = np.median(patch)
    F_inst = C_sky * gain / exptime
    A_pix = (config.PIX_SIZE_MM / config.FOCAL_MM * 206265.0) ** 2
    mu = config.ZP - 2.5 * np.log10(F_inst / A_pix)
    return mu

def measure_sky_brightness(image_path, meta_path):
    """
    High-level: read metadata, extract patch, compute mu.
    Returns tuple (mu, gain, exptime).
    """
    meta = read_metadata(meta_path)
    exp_us = float(meta.get('ExposureTime', 0))
    exptime = exp_us / 1e6
    gain = float(meta.get('AnalogueGain', 1.0)) * float(meta.get('DigitalGain', 1.0))
    patch = get_zenith_patch(image_path)
    mu = compute_sky_brightness(patch, gain, exptime)
    return mu, gain, exptime
