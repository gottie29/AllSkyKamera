#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import glob
import hashlib
import os
import random
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timedelta

import requests
from askutils import config

try:
    from askutils.utils import influx_writer
except Exception:
    influx_writer = None

try:
    from askutils.ASKsecret import API_KEY
except Exception:
    API_KEY = None


_DEFAULT_ENC_NIGHTLY_UPLOAD_API_URL = \
"aHR0cHM6Ly9hbGxza3lrYW1lcmEuc3BhY2UvYXBpL3YxL25pZ2h0bHlfdXBsb2FkLnBocA=="

FULLHD_WIDTH = 1920
MOBILE_WIDTH = 960
THUMB_WIDTH = 480
JPEG_QSCALE = 2
VIDEO_CRF = 26
VIDEO_PRESET = "medium"
VIDEO_CODEC = "libx264"
VIDEO_PIXEL_FORMAT = "yuv420p"

MIN_FILE_AGE_MINUTES = int(getattr(config, "NIGHTLY_MIN_FILE_AGE_MINUTES", 5))
STABLE_WINDOW_SECONDS = int(getattr(config, "NIGHTLY_STABLE_WINDOW_SECONDS", 90))

UPLOAD_MAX_RETRIES = int(getattr(config, "NIGHTLY_UPLOAD_MAX_RETRIES", 5))
UPLOAD_RETRY_MIN_SECONDS = int(getattr(config, "NIGHTLY_UPLOAD_RETRY_MIN_SECONDS", 300))
UPLOAD_RETRY_MAX_SECONDS = int(getattr(config, "NIGHTLY_UPLOAD_RETRY_MAX_SECONDS", 900))

HTTP_CONNECT_TIMEOUT = 120
HTTP_READ_TIMEOUT = 600
HTTP_VERIFY_SSL = True


# -----------------------------------------------------------
# Logging
# -----------------------------------------------------------
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("{0} {1}".format(ts, msg), flush=True)


# -----------------------------------------------------------
# Influx Status
# -----------------------------------------------------------
def _log_nightly_status(value, asset):
    try:
        if influx_writer is None:
            return

        kamera_id = (
            getattr(config, "CAMERAID", None)
            or getattr(config, "KAMERA_ID", None)
            or getattr(config, "KAMERA", None)
        )
        if not kamera_id:
            return

        influx_writer.log_metric(
            "uploadstatus",
            {"nightlyupload_api": float(value)},
            tags={"host": "host1", "kamera": str(kamera_id), "asset": str(asset)},
        )
    except Exception:
        pass


# -----------------------------------------------------------
# Helper
# -----------------------------------------------------------
def _get_api_url():
    return base64.b64decode(_DEFAULT_ENC_NIGHTLY_UPLOAD_API_URL).decode().strip()


def _truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _normalize_path(path):
    return os.path.abspath(os.path.expanduser(path))


def _get_camera_id():
    return (
        getattr(config, "CAMERAID", None)
        or getattr(config, "KAMERA_ID", None)
        or getattr(config, "KAMERA", None)
    )


def _latest(patterns):
    files = []
    for p in patterns:
        files.extend(glob.glob(p))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def _choose_newest_existing(*candidates):
    files = [p for p in candidates if p and os.path.isfile(p)]
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def _get_primary_base():
    allsky_path = getattr(config, "ALLSKY_PATH", "") or ""
    image_base_path = getattr(config, "IMAGE_BASE_PATH", "") or ""

    if image_base_path:
        if os.path.isabs(image_base_path):
            base = image_base_path
        else:
            base = os.path.join(allsky_path, image_base_path)
    else:
        base = allsky_path

    base = _normalize_path(base)
    log("primary_base path={0}".format(base))
    return base


def _is_age_ok(path, min_minutes):
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return False

    age_minutes = (time.time() - mtime) / 60.0
    return age_minutes >= min_minutes


def _is_size_stable(path, window_sec, poll_sec=5):
    if window_sec <= 0:
        try:
            return os.path.getsize(path) > 0
        except OSError:
            return False

    try:
        last = os.path.getsize(path)
    except OSError:
        return False

    stable_start = time.time()

    while True:
        time.sleep(min(poll_sec, max(1, window_sec)))

        try:
            now_size = os.path.getsize(path)
        except OSError:
            log("file_missing_during_stability_check path={0}".format(path))
            return False

        if now_size != last:
            last = now_size
            stable_start = time.time()

        elapsed = time.time() - stable_start
        if elapsed >= window_sec and now_size > 0:
            return True


def _file_ready(path):
    if not os.path.isfile(path):
        log("file_not_found path={0}".format(path))
        return False

    if not _is_age_ok(path, MIN_FILE_AGE_MINUTES):
        log("file_too_young path={0} required_minutes={1}".format(path, MIN_FILE_AGE_MINUTES))
        return False

    if not _is_size_stable(path, STABLE_WINDOW_SECONDS):
        log("file_not_stable path={0} stable_window_seconds={1}".format(path, STABLE_WINDOW_SECONDS))
        return False

    try:
        size = os.path.getsize(path)
    except Exception:
        size = -1

    log("file_ready path={0} size={1}".format(path, size))
    return True


# -----------------------------------------------------------
# INDI / non-INDI Asset Resolver
# -----------------------------------------------------------
def _check_candidate(path, label):
    exists = os.path.isfile(path)
    log("asset_check asset={0} path={1} exists={2}".format(label, path, "OK" if exists else "MISS"))
    return exists


def _resolve_nonindi_assets(base, date):
    assets = []

    keo = _choose_newest_existing(
        os.path.join(base, date, "keogram", "keogram-{0}.jpg".format(date)),
        os.path.join(base, date, "keogram", "keogram-{0}.png".format(date)),
    )
    if keo:
        log("asset_found asset=keogram path={0}".format(keo))
        assets.append(("keogram", keo))

    st = _choose_newest_existing(
        os.path.join(base, date, "startrails", "startrails-{0}.jpg".format(date)),
        os.path.join(base, date, "startrails", "startrails-{0}.png".format(date)),
    )
    if st:
        log("asset_found asset=startrail path={0}".format(st))
        assets.append(("startrail", st))

    mp4 = os.path.join(base, date, "allsky-{0}.mp4".format(date))
    webm = os.path.join(base, date, "allsky-{0}.webm".format(date))

    _check_candidate(mp4, "video")
    _check_candidate(webm, "video")

    if os.path.isfile(mp4):
        log("asset_found asset=video path={0}".format(mp4))
        assets.append(("video", mp4))
    elif os.path.isfile(webm):
        log("asset_found asset=video path={0}".format(webm))
        assets.append(("video", webm))

    return assets


def _resolve_indi_assets(base, date):
    assets = []

    cam_id = _get_camera_id()
    if not cam_id:
        log("indi_enabled_but_cameraid_missing")
        return assets

    date_dir = os.path.join(base, str(cam_id), "timelapse", date)
    log("indi_date_dir path={0}".format(date_dir))

    if not os.path.isdir(date_dir):
        log("indi_date_dir_missing path={0}".format(date_dir))
        return assets

    keo_patterns = [
        os.path.join(date_dir, "allsky-keogram_*_{0}_night_*.jpg".format(date)),
        os.path.join(date_dir, "allsky-keogram_*_{0}_night_*.png".format(date)),
    ]
    for p in keo_patterns:
        log("asset_pattern asset=keogram pattern={0}".format(p))
    keo = _latest(keo_patterns)
    if keo:
        log("asset_found asset=keogram path={0}".format(keo))
        assets.append(("keogram", keo))

    st_patterns = [
        os.path.join(date_dir, "allsky-startrail_*_{0}_night_*.jpg".format(date)),
        os.path.join(date_dir, "allsky-startrail_*_{0}_night_*.png".format(date)),
    ]
    for p in st_patterns:
        log("asset_pattern asset=startrail pattern={0}".format(p))
    st = _latest(st_patterns)
    if st:
        log("asset_found asset=startrail path={0}".format(st))
        assets.append(("startrail", st))

    tl_patterns = [
        os.path.join(date_dir, "allsky-timelapse_*_{0}_night_*.mp4".format(date)),
        os.path.join(date_dir, "allsky-timelapse_*_{0}_night_*.webm".format(date)),
    ]
    for p in tl_patterns:
        log("asset_pattern asset=video pattern={0}".format(p))
    tl = _latest(tl_patterns)
    if tl:
        log("asset_found asset=video path={0}".format(tl))
        assets.append(("video", tl))

    return assets


# -----------------------------------------------------------
# ffmpeg helpers
# -----------------------------------------------------------
def _scale_filter(w):
    return "scale='if(gt(iw,{0}),{0},iw)':-2".format(w)


def _create_jpg(src, dst, width):
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", src,
        "-frames:v", "1",
        "-vf", _scale_filter(width),
        "-q:v", str(JPEG_QSCALE),
        "-pix_fmt", "yuvj420p",
        dst
    ]
    subprocess.check_call(cmd)


def _create_three(src, tmp):
    f = os.path.join(tmp, "fullhd.jpg")
    m = os.path.join(tmp, "mobile.jpg")
    t = os.path.join(tmp, "thumb.jpg")

    _create_jpg(src, f, FULLHD_WIDTH)
    _create_jpg(src, m, MOBILE_WIDTH)
    _create_jpg(src, t, THUMB_WIDTH)

    return dict(fullhd=f, mobile=m, thumb=t)


def _video_duration(path):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]
    out = subprocess.check_output(cmd).decode().strip()
    return float(out)


def _reduce_video(src, dst):
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", src,
        "-vf", _scale_filter(FULLHD_WIDTH),
        "-c:v", VIDEO_CODEC,
        "-preset", VIDEO_PRESET,
        "-crf", str(VIDEO_CRF),
        "-pix_fmt", VIDEO_PIXEL_FORMAT,
        "-profile:v", "main",
        "-level", "4.0",
        "-movflags", "+faststart",
        "-an",
        dst
    ]
    subprocess.check_call(cmd)


def _video_thumb(src, dst):
    mid = _video_duration(src) / 2.0

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", str(mid),
        "-i", src,
        "-frames:v", "1",
        "-vf", _scale_filter(MOBILE_WIDTH),
        "-q:v", str(JPEG_QSCALE),
        dst
    ]
    subprocess.check_call(cmd)


def _prepare_video(src, tmp):
    ext = os.path.splitext(src)[1].lower()
    reduced = os.path.join(tmp, "video" + ext)
    thumb = os.path.join(tmp, "thumb.jpg")

    _reduce_video(src, reduced)

    src_size = os.path.getsize(src)
    reduced_size = os.path.getsize(reduced)

    if reduced_size >= src_size * 0.95:
        final_video = os.path.join(tmp, "video_original" + ext)
        shutil.copy2(src, final_video)
        _video_thumb(final_video, thumb)
        log("video_keep_original original_size={0} reduced_size={1}".format(src_size, reduced_size))
        return final_video, thumb

    _video_thumb(reduced, thumb)
    log("video_use_reduced original_size={0} reduced_size={1}".format(src_size, reduced_size))
    return reduced, thumb


# -----------------------------------------------------------
# Upload
# -----------------------------------------------------------
def _upload(asset, date, datafiles, publish_last):
    url = _get_api_url()

    if not API_KEY:
        log("API_KEY fehlt")
        return False

    headers = {"X-API-Key": API_KEY}

    def _video_mime(path):
        ext = os.path.splitext(path)[1].lower()
        if ext == ".webm":
            return "video/webm"
        return "video/mp4"

    try:
        if asset == "video":
            v, t = datafiles

            if not os.path.isfile(v):
                log("upload_missing_video_file path={0}".format(v))
                return False
            if not os.path.isfile(t):
                log("upload_missing_video_thumb path={0}".format(t))
                return False

            video_size = os.path.getsize(v)
            thumb_size = os.path.getsize(t)
            video_mime = _video_mime(v)

            log(
                "upload_video_prepare asset={0} file={1} mime={2} video_size={3} thumb_size={4}".format(
                    asset, os.path.basename(v), video_mime, video_size, thumb_size
                )
            )

            with open(v, "rb") as fh_video, open(t, "rb") as fh_thumb:
                files = {
                    "file": (os.path.basename(v), fh_video, video_mime),
                    "thumb": ("thumb.jpg", fh_thumb, "image/jpeg"),
                }

                data = {
                    "date": date,
                    "asset": asset,
                    "publish_last": "1" if publish_last else "0",
                    "kamera": str(_get_camera_id() or ""),
                }

                r = requests.post(
                    url,
                    headers=headers,
                    data=data,
                    files=files,
                    timeout=(HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT),
                    verify=HTTP_VERIFY_SSL,
                )

        else:
            fullhd = datafiles["fullhd"]
            mobile = datafiles["mobile"]
            thumb = datafiles["thumb"]

            for p in (fullhd, mobile, thumb):
                if not os.path.isfile(p):
                    log("upload_missing_image_variant path={0}".format(p))
                    return False

            log(
                "upload_image_prepare asset={0} fullhd_size={1} mobile_size={2} thumb_size={3}".format(
                    asset,
                    os.path.getsize(fullhd),
                    os.path.getsize(mobile),
                    os.path.getsize(thumb),
                )
            )

            with open(fullhd, "rb") as fh_fullhd, \
                 open(mobile, "rb") as fh_mobile, \
                 open(thumb, "rb") as fh_thumb:

                files = {
                    "fullhd": ("fullhd.jpg", fh_fullhd, "image/jpeg"),
                    "mobile": ("mobile.jpg", fh_mobile, "image/jpeg"),
                    "thumb": ("thumb.jpg", fh_thumb, "image/jpeg"),
                }

                data = {
                    "date": date,
                    "asset": asset,
                    "publish_last": "1" if publish_last else "0",
                    "kamera": str(_get_camera_id() or ""),
                }

                r = requests.post(
                    url,
                    headers=headers,
                    data=data,
                    files=files,
                    timeout=(HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT),
                    verify=HTTP_VERIFY_SSL,
                )

    except requests.RequestException as e:
        log("upload_request_exception {0} error={1}".format(asset, e))
        return False
    except Exception as e:
        log("upload_prepare_exception {0} error={1}".format(asset, e))
        return False

    if r.status_code != 200:
        body = (r.text or "")[:1000].replace("\n", " ").replace("\r", " ")
        log("upload_http_error {0} asset={1} body={2}".format(r.status_code, asset, body))

        try:
            j = r.json()
            retry_after = j.get("retry_after_seconds")
            if retry_after is not None:
                log("upload_retry_after_hint {0}".format(retry_after))
        except Exception:
            pass

        return False

    try:
        j = r.json()
    except Exception:
        log("invalid_json asset={0} body={1}".format(asset, (r.text or "")[:500]))
        return False

    if j.get("ok") is not True:
        log("upload_not_ok asset={0} body={1}".format(asset, str(j)[:1000]))
        return False

    log("upload_ok asset={0}".format(asset))
    return True


# -----------------------------------------------------------
# Asset Scan
# -----------------------------------------------------------
def _collect(date):
    primary_base = _get_primary_base()
    assets = []
    indi_flag = _truthy(getattr(config, "INDI", 0))

    log("collect_start date={0} indi={1}".format(date, indi_flag))

    if not indi_flag:
        assets = _resolve_nonindi_assets(primary_base, date)
    else:
        assets = _resolve_indi_assets(primary_base, date)

    if assets:
        for asset_name, asset_path in assets:
            log("collect_ok asset={0} path={1}".format(asset_name, asset_path))
    else:
        log("collect_no_assets_found")

    return assets


# -----------------------------------------------------------
# Jitter
# -----------------------------------------------------------
def _apply_jitter(date):
    window = int(getattr(config, "NIGHTLY_UPLOAD_JITTER_MAX_SECONDS", 3600))
    if window <= 0:
        log("jitter_seconds=0")
        return

    kamera = _get_camera_id() or "ASK000"
    seed = "{0}|{1}".format(kamera, date).encode()
    slot = int(hashlib.sha256(seed).hexdigest()[:8], 16) % window
    log("jitter_seconds={0}".format(slot))
    time.sleep(slot)


# -----------------------------------------------------------
# Main
# -----------------------------------------------------------
def upload_nightly_batch(date=None):
    if date is None:
        date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    log("nightly_start {0}".format(date))

    assets = _collect(date)

    if not assets:
        log("no_assets")
        _log_nightly_status(3, "batch")
        return False

    prepared = []

    for asset, path in assets:
        log("prepare_start asset={0} path={1}".format(asset, path))

        if not _file_ready(path):
            log("prepare_skip_not_ready asset={0} path={1}".format(asset, path))
            _log_nightly_status(4, asset)
            continue

        tmp = tempfile.mkdtemp(prefix="nightly_{0}_".format(asset))

        try:
            if asset in ("keogram", "startrail"):
                variants = _create_three(path, tmp)
                prepared.append(dict(asset=asset, files=variants, tmp=tmp))

            elif asset == "video":
                video, thumb = _prepare_video(path, tmp)
                prepared.append(dict(asset=asset, files=(video, thumb), tmp=tmp))

            log("prepare_ok asset={0}".format(asset))

        except Exception as e:
            log("prepare_failed asset={0} error={1}".format(asset, e))
            _log_nightly_status(2, asset)
            shutil.rmtree(tmp, ignore_errors=True)

    if not prepared:
        log("nothing_prepared")
        _log_nightly_status(2, "batch")
        return False

    _apply_jitter(date)

    any_success = False

    for job in prepared:
        asset = job["asset"]
        files = job["files"]

        ok = False

        for attempt in range(1, UPLOAD_MAX_RETRIES + 1):
            log("upload asset={0} attempt={1}/{2}".format(asset, attempt, UPLOAD_MAX_RETRIES))

            if _upload(asset, date, files, True):
                ok = True
                any_success = True
                _log_nightly_status(1, asset)
                break

            if attempt < UPLOAD_MAX_RETRIES:
                delay = random.randint(
                    UPLOAD_RETRY_MIN_SECONDS,
                    UPLOAD_RETRY_MAX_SECONDS
                )
                log("retry_in {0}".format(delay))
                time.sleep(delay)

        if not ok:
            log("upload_failed asset={0}".format(asset))
            _log_nightly_status(2, asset)

        shutil.rmtree(job["tmp"], ignore_errors=True)

    log("nightly_done")

    if any_success:
        _log_nightly_status(1, "batch")
    else:
        _log_nightly_status(2, "batch")

    return any_success