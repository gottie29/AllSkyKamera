#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import shutil
from collections import deque
from datetime import datetime, date, timedelta

import numpy as np
from PIL import Image

from askutils import config


def log(msg):
    print(msg, flush=True)


def _utc_now_iso():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_mkdir(path):
    if path and not os.path.isdir(path):
        os.makedirs(path)


def _read_json(path, default_value):
    if not os.path.isfile(path):
        return default_value
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_value


def _write_runtime_status(data):
    status_path = os.path.join(_get_output_dir(), "last_run.json")
    _safe_mkdir(_get_output_dir())
    _write_json(status_path, data)

def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _get_kamera_id():
    return str(getattr(config, "KAMERA_ID", None) or getattr(config, "KAMERA", None) or "")


def _get_source_images_dir():
    # TJ-Kameras: ALLSKY_PATH + IMAGE_BASE_PATH
    return os.path.join(config.ALLSKY_PATH, config.IMAGE_BASE_PATH)


def _get_output_dir():
    return getattr(config, "METEOR_OUTPUT_DIR", "/home/pi/AllSkyKamera/meteordetect")


def _get_state_file():
    return getattr(config, "METEOR_STATE_FILE", "/home/pi/AllSkyKamera/meteordetect/meteor_state.json")


def _load_state():
    return _read_json(_get_state_file(), {})


def _save_state(state):
    state_file = _get_state_file()
    _safe_mkdir(os.path.dirname(state_file))
    _write_json(state_file, state)


def _list_day_dirs():
    base_dir = _get_source_images_dir()
    days = []

    if not os.path.isdir(base_dir):
        return days

    for name in sorted(os.listdir(base_dir)):
        path = os.path.join(base_dir, name)
        if os.path.isdir(path) and re.match(r"^\d{8}$", name):
            days.append(name)

    return days


def _get_active_day_dir():
    days = _list_day_dirs()
    if not days:
        return None
    return days[-1]


def _extract_timestamp_from_filename(filename):
    m = re.match(r"^image-(\d{14})\.(jpg|jpeg|png)$", filename, re.IGNORECASE)
    if not m:
        return None
    return m.group(1)


def _extract_time_from_filename(filename):
    ts = _extract_timestamp_from_filename(filename)
    if not ts:
        return None
    return ts[8:14]


def _list_images_for_day(day_dir_name):
    day_path = os.path.join(_get_source_images_dir(), day_dir_name)
    if not os.path.isdir(day_path):
        return []

    files = []
    for name in sorted(os.listdir(day_path)):
        if re.search(r"\.(jpg|jpeg|png)$", name, re.IGNORECASE):
            files.append(os.path.join(day_path, name))
    return files


def _find_start_index(image_paths, last_processed_image):
    if not last_processed_image:
        return 0

    last_name = os.path.basename(last_processed_image)
    for i, path in enumerate(image_paths):
        if os.path.basename(path) == last_name:
            return i + 1
    return 0


def _load_image_rgb(path):
    img = Image.open(path).convert("RGB")
    return np.array(img, dtype=np.uint8)


def _rgb_to_gray(img):
    return (
        0.299 * img[:, :, 0] +
        0.587 * img[:, :, 1] +
        0.114 * img[:, :, 2]
    ).astype(np.uint8)


def _create_circle_mask(height, width):
    cy = height // 2
    cx = width // 2
    radius = height // 2

    y, x = np.ogrid[:height, :width]
    dist2 = (x - cx) ** 2 + (y - cy) ** 2
    return dist2 <= radius ** 2


def _detect_positive_motion(img1, img2, threshold, circle_mask):
    gray1 = _rgb_to_gray(img1).astype(np.int16)
    gray2 = _rgb_to_gray(img2).astype(np.int16)

    diff = gray2 - gray1
    thresh = np.where(diff >= threshold, 255, 0).astype(np.uint8)
    thresh = np.where(circle_mask, thresh, 0).astype(np.uint8)

    count = int(np.count_nonzero(thresh))
    total_mask_pixels = int(np.count_nonzero(circle_mask))
    percent = (float(count) / float(total_mask_pixels) * 100.0) if total_mask_pixels > 0 else 0.0

    return count, percent, thresh


def _find_connected_components(binary_mask):
    h, w = binary_mask.shape
    visited = np.zeros((h, w), dtype=np.uint8)
    components = []

    ys, xs = np.where(binary_mask > 0)

    for start_y, start_x in zip(ys, xs):
        if visited[start_y, start_x]:
            continue

        q = deque()
        q.append((int(start_y), int(start_x)))
        visited[start_y, start_x] = 1

        min_x = max_x = int(start_x)
        min_y = max_y = int(start_y)
        area = 0

        while q:
            y, x = q.popleft()
            area += 1

            if x < min_x:
                min_x = x
            if x > max_x:
                max_x = x
            if y < min_y:
                min_y = y
            if y > max_y:
                max_y = y

            for ny in (y - 1, y, y + 1):
                if ny < 0 or ny >= h:
                    continue
                for nx in (x - 1, x, x + 1):
                    if nx < 0 or nx >= w:
                        continue
                    if visited[ny, nx]:
                        continue
                    if binary_mask[ny, nx] == 0:
                        continue
                    visited[ny, nx] = 1
                    q.append((ny, nx))

        width = max_x - min_x + 1
        height = max_y - min_y + 1
        long_side = max(width, height)
        short_side = max(1, min(width, height))
        aspect_ratio = float(long_side) / float(short_side)

        components.append({
            "area": int(area),
            "min_x": int(min_x),
            "max_x": int(max_x),
            "min_y": int(min_y),
            "max_y": int(max_y),
            "width": int(width),
            "height": int(height),
            "long_side": int(long_side),
            "short_side": int(short_side),
            "aspect_ratio": float(aspect_ratio),
        })

    return components


def _filter_line_components(components):
    min_blob_pixels = int(getattr(config, "METEOR_MIN_BLOB_PIXELS", 25))
    min_line_length = int(getattr(config, "METEOR_MIN_LINE_LENGTH", 20))
    min_aspect_ratio = float(getattr(config, "METEOR_MIN_ASPECT_RATIO", 4.0))

    good = []
    for c in components:
        if c["area"] < min_blob_pixels:
            continue
        if c["long_side"] < min_line_length:
            continue
        if c["aspect_ratio"] < min_aspect_ratio:
            continue
        good.append(c)
    return good


def _resize_image(img_pil, target_width):
    if not target_width:
        return img_pil.copy()
    if img_pil.width <= target_width:
        return img_pil.copy()
    ratio = float(target_width) / float(img_pil.width)
    new_height = int(img_pil.height * ratio)
    return img_pil.resize((int(target_width), int(new_height)), Image.BILINEAR)


def _draw_boxes_on_image(img_pil, components):
    arr = np.array(img_pil.convert("RGB"), dtype=np.uint8)
    h, w = arr.shape[:2]

    for c in components:
        x1 = max(0, min(w - 1, c["min_x"]))
        x2 = max(0, min(w - 1, c["max_x"]))
        y1 = max(0, min(h - 1, c["min_y"]))
        y2 = max(0, min(h - 1, c["max_y"]))

        arr[y1:min(y1 + 2, h), x1:x2 + 1] = [255, 0, 0]
        arr[max(y2 - 1, 0):y2 + 1, x1:x2 + 1] = [255, 0, 0]
        arr[y1:y2 + 1, x1:min(x1 + 2, w)] = [255, 0, 0]
        arr[y1:y2 + 1, max(x2 - 1, 0):x2 + 1] = [255, 0, 0]

    return Image.fromarray(arr)


def _get_day_output_dir(day_dir_name):
    return os.path.join(_get_output_dir(), day_dir_name)


def _get_day_index_path(day_dir_name):
    return os.path.join(_get_day_output_dir(day_dir_name), "index.json")


def _candidate_dir(day_dir_name, candidate_id):
    return os.path.join(_get_day_output_dir(day_dir_name), candidate_id)


def _quicklook_dir(day_dir_name):
    return os.path.join(_get_day_output_dir(day_dir_name), "quicklook")


def _candidate_json_path(day_dir_name, candidate_id):
    return os.path.join(_candidate_dir(day_dir_name, candidate_id), "candidate.json")


def _candidate_uploaded_marker(day_dir_name, candidate_id):
    return os.path.join(_candidate_dir(day_dir_name, candidate_id), "uploaded.ok")


def _save_candidate(day_dir_name, prev_path, curr_path, diff_img, pixel_count, pixel_percent, line_components):
    kamera = _get_kamera_id()
    fullhd_width = int(getattr(config, "METEOR_FULLHD_WIDTH", 1920))
    small_width = int(getattr(config, "METEOR_SMALL_WIDTH", 640))
    diff_width = int(getattr(config, "METEOR_DIFF_WIDTH", 640))
    boxed_width = int(getattr(config, "METEOR_BOXED_WIDTH", 640))
    prev_small_width = int(getattr(config, "METEOR_PREV_SMALL_WIDTH", 640))

    base_curr = os.path.splitext(os.path.basename(curr_path))[0]
    candidate_id = base_curr

    day_output_dir = _get_day_output_dir(day_dir_name)
    candidate_dir = _candidate_dir(day_dir_name, candidate_id)
    quicklook_dir = _quicklook_dir(day_dir_name)

    _safe_mkdir(day_output_dir)
    _safe_mkdir(candidate_dir)
    _safe_mkdir(quicklook_dir)

    prev_img = Image.open(prev_path).convert("RGB")
    curr_img = Image.open(curr_path).convert("RGB")
    diff_pil = Image.fromarray(diff_img)
    boxed_pil = _draw_boxes_on_image(curr_img, line_components)

    curr_fullhd_name = "current_fullhd.jpg"
    curr_small_name = "current_small.jpg"
    prev_small_name = "previous_small.jpg"
    diff_small_name = "diff_small.jpg"
    boxed_small_name = "boxed_small.jpg"

    _resize_image(curr_img, fullhd_width).save(os.path.join(candidate_dir, curr_fullhd_name), quality=90)
    _resize_image(curr_img, small_width).save(os.path.join(candidate_dir, curr_small_name), quality=85)
    _resize_image(prev_img, prev_small_width).save(os.path.join(candidate_dir, prev_small_name), quality=85)
    _resize_image(diff_pil, diff_width).save(os.path.join(candidate_dir, diff_small_name), quality=85)
    _resize_image(boxed_pil, boxed_width).save(os.path.join(candidate_dir, boxed_small_name), quality=85)

    quicklook_name = candidate_id + "_small.jpg"
    _resize_image(boxed_pil, small_width).save(os.path.join(quicklook_dir, quicklook_name), quality=85)

    best = None
    if line_components:
        best = sorted(
            line_components,
            key=lambda c: (c["aspect_ratio"], c["long_side"], c["area"]),
            reverse=True
        )[0]

    candidate_data = {
        "kamera": kamera,
        "day": day_dir_name,
        "candidate_id": candidate_id,
        "created_utc": _utc_now_iso(),
        "source_previous_image": os.path.basename(prev_path),
        "source_current_image": os.path.basename(curr_path),
        "source_timestamp": _extract_timestamp_from_filename(os.path.basename(curr_path)),
        "source_time": _extract_time_from_filename(os.path.basename(curr_path)),
        "pixel_count": int(pixel_count),
        "pixel_percent": float(pixel_percent),
        "threshold": int(getattr(config, "METEOR_THRESHOLD", 80)),
        "min_pixels": int(getattr(config, "METEOR_MIN_PIXELS", 1200)),
        "min_blob_pixels": int(getattr(config, "METEOR_MIN_BLOB_PIXELS", 25)),
        "min_line_length": int(getattr(config, "METEOR_MIN_LINE_LENGTH", 20)),
        "min_aspect_ratio": float(getattr(config, "METEOR_MIN_ASPECT_RATIO", 4.0)),
        "line_components": line_components,
        "best_line": best,
        "uploaded": False,
        "uploaded_utc": None,
        "files": {
            "current_fullhd": curr_fullhd_name,
            "current_small": curr_small_name,
            "previous_small": prev_small_name,
            "diff_small": diff_small_name,
            "boxed_small": boxed_small_name,
            "quicklook": os.path.join("quicklook", quicklook_name),
        }
    }

    _write_json(_candidate_json_path(day_dir_name, candidate_id), candidate_data)
    return candidate_id


def _rebuild_day_index(day_dir_name):
    day_output_dir = _get_day_output_dir(day_dir_name)
    _safe_mkdir(day_output_dir)

    candidates = []
    for name in sorted(os.listdir(day_output_dir)):
        path = os.path.join(day_output_dir, name)
        if not os.path.isdir(path):
            continue
        if name == "quicklook":
            continue

        candidate_json = os.path.join(path, "candidate.json")
        if not os.path.isfile(candidate_json):
            continue

        data = _read_json(candidate_json, None)
        if not isinstance(data, dict):
            continue

        candidates.append({
            "candidate_id": data.get("candidate_id"),
            "source_current_image": data.get("source_current_image"),
            "source_previous_image": data.get("source_previous_image"),
            "source_time": data.get("source_time"),
            "pixel_count": data.get("pixel_count"),
            "pixel_percent": data.get("pixel_percent"),
            "best_line": data.get("best_line"),
            "uploaded": data.get("uploaded", False),
            "uploaded_utc": data.get("uploaded_utc"),
            "files": data.get("files", {}),
        })

    index_data = {
        "kamera": _get_kamera_id(),
        "day": day_dir_name,
        "updated_utc": _utc_now_iso(),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }

    _write_json(_get_day_index_path(day_dir_name), index_data)


def _mark_candidate_uploaded(day_dir_name, candidate_id):
    candidate_json_path = _candidate_json_path(day_dir_name, candidate_id)
    data = _read_json(candidate_json_path, None)
    if isinstance(data, dict):
        data["uploaded"] = True
        data["uploaded_utc"] = _utc_now_iso()
        _write_json(candidate_json_path, data)

    marker = _candidate_uploaded_marker(day_dir_name, candidate_id)
    with open(marker, "w", encoding="utf-8") as f:
        f.write(_utc_now_iso() + "\n")


def _detect_candidates_for_day(day_dir_name):
    image_paths = _list_images_for_day(day_dir_name)

    _safe_mkdir(_get_output_dir())

    state = _load_state()
    state_day = state.get("last_day_dir")
    state_last_image = state.get("last_processed_image")

    first_run_for_day = (state_day != day_dir_name) or (not state_last_image)

    if first_run_for_day:
        lookback_minutes = int(getattr(config, "METEOR_INITIAL_LOOKBACK_MINUTES", 30))
        image_paths = _filter_to_recent_images(image_paths, lookback_minutes)
        start_index = 1 if len(image_paths) >= 2 else 0
    else:
        start_index = _find_start_index(image_paths, state_last_image)
        if start_index < 1:
            start_index = 1

    if len(image_paths) < 2:
        state["last_day_dir"] = day_dir_name
        state["last_processed_image"] = state_last_image
        state["last_run_utc"] = _utc_now_iso()
        state["mode"] = "initial_lookback" if first_run_for_day else "incremental"
        state["images_in_scope"] = len(image_paths)
        _save_state(state)

        _write_runtime_status({
            "ok": True,
            "day": day_dir_name,
            "mode": "initial_lookback" if first_run_for_day else "incremental",
            "images_in_scope": len(image_paths),
            "comparisons": 0,
            "new_candidates": 0,
            "last_processed_image": state_last_image,
            "updated_utc": _utc_now_iso(),
            "message": "Nicht genug Bilder im aktuellen Fenster"
        })

        log("Meteor: nicht genug Bilder im aktuellen Fenster.")
        return {
            "day": day_dir_name,
            "new_candidates": 0,
            "last_processed_image": state_last_image,
            "comparisons": 0,
        }

    threshold = int(getattr(config, "METEOR_THRESHOLD", 80))
    min_pixels = int(getattr(config, "METEOR_MIN_PIXELS", 1200))

    comparisons = 0
    new_candidates = 0
    circle_mask = None
    last_processed_image = state_last_image

    for i in range(start_index, len(image_paths)):
        prev_path = image_paths[i - 1]
        curr_path = image_paths[i]

        try:
            img_prev = _load_image_rgb(prev_path)
            img_curr = _load_image_rgb(curr_path)

            if img_prev.shape != img_curr.shape:
                log("Meteor: unterschiedliche Bildgroessen, übersprungen: %s / %s" % (
                    os.path.basename(prev_path),
                    os.path.basename(curr_path)
                ))
                last_processed_image = os.path.basename(curr_path)
                comparisons += 1
                continue

            if circle_mask is None:
                height, width = img_prev.shape[:2]
                circle_mask = _create_circle_mask(height, width)

            pixel_count, pixel_percent, thresh = _detect_positive_motion(
                img_prev, img_curr, threshold, circle_mask
            )

            components = _find_connected_components(thresh)
            line_components = _filter_line_components(components)

            if pixel_count >= min_pixels and len(line_components) > 0:
                candidate_id = _save_candidate(
                    day_dir_name,
                    prev_path,
                    curr_path,
                    thresh,
                    pixel_count,
                    pixel_percent,
                    line_components
                )
                new_candidates += 1
                log("Meteor: Kandidat erkannt %s | pixel=%s | lines=%s" % (
                    candidate_id, pixel_count, len(line_components)
                ))
            else:
                log("Meteor: kein Kandidat %s | pixel=%s | lines=%s" % (
                    os.path.basename(curr_path), pixel_count, len(line_components)
                ))

            last_processed_image = os.path.basename(curr_path)
            comparisons += 1

        except Exception as e:
            log("Meteor: Fehler bei %s: %s" % (os.path.basename(curr_path), str(e)))
            last_processed_image = os.path.basename(curr_path)
            comparisons += 1

    if last_processed_image:
        state["last_processed_image"] = last_processed_image

    state["last_day_dir"] = day_dir_name
    state["last_run_utc"] = _utc_now_iso()
    state["mode"] = "initial_lookback" if first_run_for_day else "incremental"
    state["images_in_scope"] = len(image_paths)
    state["comparisons"] = comparisons
    state["new_candidates"] = new_candidates
    _save_state(state)

    _rebuild_day_index(day_dir_name)

    _write_runtime_status({
        "ok": True,
        "day": day_dir_name,
        "mode": "initial_lookback" if first_run_for_day else "incremental",
        "images_in_scope": len(image_paths),
        "comparisons": comparisons,
        "new_candidates": new_candidates,
        "last_processed_image": state.get("last_processed_image"),
        "updated_utc": _utc_now_iso(),
    })

    return {
        "day": day_dir_name,
        "new_candidates": new_candidates,
        "last_processed_image": state.get("last_processed_image"),
        "comparisons": comparisons,
    }

def cleanup_old_meteor_dirs():
    keep_days = int(getattr(config, "METEOR_KEEP_DAYS_LOCAL", 3))
    output_dir = _get_output_dir()
    if keep_days <= 0 or not os.path.isdir(output_dir):
        return

    today = date.today()

    for name in os.listdir(output_dir):
        path = os.path.join(output_dir, name)
        if not os.path.isdir(path):
            continue
        if not re.match(r"^\d{8}$", name):
            continue

        try:
            d = datetime.strptime(name, "%Y%m%d").date()
        except Exception:
            continue

        age_days = (today - d).days
        if age_days > keep_days:
            try:
                shutil.rmtree(path)
                log("Meteor: altes Verzeichnis geloescht: %s" % path)
            except Exception as e:
                log("Meteor: Fehler beim Loeschen von %s: %s" % (path, str(e)))

def _filter_to_recent_images(image_paths, lookback_minutes):
    if not image_paths:
        return []

    if lookback_minutes <= 0:
        return image_paths

    dated = []
    for path in image_paths:
        dt = _extract_datetime_from_filename(os.path.basename(path))
        if dt is not None:
            dated.append((path, dt))

    if not dated:
        return image_paths

    newest_dt = dated[-1][1]
    cutoff = newest_dt - timedelta(minutes=int(lookback_minutes))

    filtered = [path for path, dt in dated if dt >= cutoff]
    return filtered

def _extract_datetime_from_filename(filename):
    ts = _extract_timestamp_from_filename(filename)
    if not ts:
        return None
    try:
        return datetime.strptime(ts, "%Y%m%d%H%M%S")
    except Exception:
        return None

def upload_pending_for_day(day_dir_name):
    try:
        from askutils.uploader.meteor_upload_api import upload_pending_meteor_candidates
    except Exception as e:
        log("Meteor: Upload-Modul konnte nicht geladen werden: %s" % str(e))
        return

    day_dir = _get_day_output_dir(day_dir_name)
    if not os.path.isdir(day_dir):
        return

    uploaded_ids = upload_pending_meteor_candidates(day_dir_name, day_dir)

    if uploaded_ids:
        for candidate_id in uploaded_ids:
            _mark_candidate_uploaded(day_dir_name, candidate_id)
        _rebuild_day_index(day_dir_name)

def _has_pending_uploads(day_dir_name):
    day_dir = _get_day_output_dir(day_dir_name)
    if not os.path.isdir(day_dir):
        return False

    for name in os.listdir(day_dir):
        candidate_dir = os.path.join(day_dir, name)
        if not os.path.isdir(candidate_dir):
            continue
        if name == "quicklook":
            continue

        candidate_json = os.path.join(candidate_dir, "candidate.json")
        uploaded_ok = os.path.join(candidate_dir, "uploaded.ok")

        if os.path.isfile(candidate_json) and not os.path.isfile(uploaded_ok):
            return True

    return False

def run_meteor_detection_cycle():
    if not bool(getattr(config, "METEOR_ENABLE", False)):
        log("Meteor: deaktiviert in config.")
        return False

    output_dir = _get_output_dir()
    _safe_mkdir(output_dir)

    active_day = _get_active_day_dir()
    if not active_day:
        log("Meteor: kein aktives Tagesverzeichnis gefunden.")
        return False

    log("Meteor: aktiver Tagesordner = %s" % active_day)

    result = _detect_candidates_for_day(active_day)
    comparisons = int(result.get("comparisons", 0) or 0)
    new_candidates = int(result.get("new_candidates", 0) or 0)

    log("Meteor: Vergleiche=%s, neue Kandidaten=%s" % (
        comparisons,
        new_candidates
    ))

    if _has_pending_uploads(active_day):
        upload_pending_for_day(active_day)
    else:
        log("Meteor: keine offenen Uploads.")

    cleanup_old_meteor_dirs()
    return True