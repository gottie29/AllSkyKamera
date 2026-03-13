#!/usr/bin/env python3

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
from typing import Dict, List, Optional, Tuple

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

MIN_FILE_AGE_MINUTES = int(getattr(config,"NIGHTLY_MIN_FILE_AGE_MINUTES",5))
STABLE_WINDOW_SECONDS = int(getattr(config,"NIGHTLY_STABLE_WINDOW_SECONDS",90))

UPLOAD_MAX_RETRIES = int(getattr(config,"NIGHTLY_UPLOAD_MAX_RETRIES",5))
UPLOAD_RETRY_MIN_SECONDS = int(getattr(config,"NIGHTLY_UPLOAD_RETRY_MIN_SECONDS",300))
UPLOAD_RETRY_MAX_SECONDS = int(getattr(config,"NIGHTLY_UPLOAD_RETRY_MAX_SECONDS",900))

HTTP_CONNECT_TIMEOUT = 20
HTTP_READ_TIMEOUT = 300
HTTP_VERIFY_SSL = True

# -----------------------------------------------------------
# Logging
# -----------------------------------------------------------
def log(msg:str):
    ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ts} {msg}",flush=True)

# -----------------------------------------------------------
# Helper
# -----------------------------------------------------------
def _get_api_url():
    return base64.b64decode(_DEFAULT_ENC_NIGHTLY_UPLOAD_API_URL).decode()

def _truthy(v):
    return str(v).lower() in ("1","true","yes","on")

def _file_ready(path:str)->bool:
    if not os.path.isfile(path):
        return False
    try:
        mtime=os.path.getmtime(path)
    except:
        return False
    age=(time.time()-mtime)/60.0
    if age<MIN_FILE_AGE_MINUTES:
        return False

    size1=os.path.getsize(path)
    time.sleep(5)
    size2=os.path.getsize(path)

    return size1==size2 and size2>0

def _latest(patterns):
    files=[]
    for p in patterns:
        files.extend(glob.glob(p))
    if not files:
        return None
    return max(files,key=os.path.getmtime)

# -----------------------------------------------------------
# ffmpeg helpers
# -----------------------------------------------------------
def _scale_filter(w):
    return f"scale='if(gt(iw,{w}),{w},iw)':-2"

def _create_jpg(src,dst,width):
    cmd=[
        "ffmpeg","-hide_banner","-loglevel","error","-y",
        "-i",src,
        "-frames:v","1",
        "-vf",_scale_filter(width),
        "-q:v",str(JPEG_QSCALE),
        "-pix_fmt","yuvj420p",
        dst
    ]
    subprocess.check_call(cmd)

def _create_three(src,tmp):
    f=os.path.join(tmp,"fullhd.jpg")
    m=os.path.join(tmp,"mobile.jpg")
    t=os.path.join(tmp,"thumb.jpg")

    _create_jpg(src,f,FULLHD_WIDTH)
    _create_jpg(src,m,MOBILE_WIDTH)
    _create_jpg(src,t,THUMB_WIDTH)

    return dict(fullhd=f,mobile=m,thumb=t)

def _video_duration(path):
    cmd=[
        "ffprobe","-v","error",
        "-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1",
        path
    ]

    out=subprocess.check_output(cmd).decode().strip()

    return float(out)

def _reduce_video(src,dst):
    cmd=[
        "ffmpeg","-hide_banner","-loglevel","error","-y",
        "-i",src,
        "-vf",_scale_filter(FULLHD_WIDTH),
        "-c:v",VIDEO_CODEC,
        "-preset",VIDEO_PRESET,
        "-crf",str(VIDEO_CRF),
        "-pix_fmt",VIDEO_PIXEL_FORMAT,
        "-movflags","+faststart",
        "-an",
        dst
    ]

    subprocess.check_call(cmd)

def _video_thumb(src,dst):
    mid=_video_duration(src)/2.0

    cmd=[
        "ffmpeg","-hide_banner","-loglevel","error","-y",
        "-ss",str(mid),
        "-i",src,
        "-frames:v","1",
        "-vf",_scale_filter(MOBILE_WIDTH),
        "-q:v",str(JPEG_QSCALE),
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
        log(f"video_keep_original original_size={src_size} reduced_size={reduced_size}")
        return final_video, thumb

    _video_thumb(reduced, thumb)
    log(f"video_use_reduced original_size={src_size} reduced_size={reduced_size}")
    return reduced, thumb

# -----------------------------------------------------------
# Upload
# -----------------------------------------------------------
def _upload(asset, date, datafiles, publish_last):
    url = _get_api_url()
    headers = {"X-API-Key": API_KEY}

    def _video_mime(path: str) -> str:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".webm":
            return "video/webm"
        return "video/mp4"

    try:
        if asset == "video":
            v, t = datafiles

            if not os.path.isfile(v):
                log(f"upload_missing_video_file path={v}")
                return False
            if not os.path.isfile(t):
                log(f"upload_missing_video_thumb path={t}")
                return False

            video_size = os.path.getsize(v)
            thumb_size = os.path.getsize(t)
            video_mime = _video_mime(v)

            log(
                f"upload_video_prepare file={os.path.basename(v)} "
                f"mime={video_mime} video_size={video_size} thumb_size={thumb_size}"
            )

            with open(v, "rb") as fh_video, open(t, "rb") as fh_thumb:
                files = {
                    "file": (os.path.basename(v), fh_video, video_mime),
                    "thumb": ("thumb.jpg", fh_thumb, "image/jpeg"),
                }

                r = requests.post(
                    url,
                    headers=headers,
                    data={
                        "date": date,
                        "asset": asset,
                        "publish_last": "1" if publish_last else "0",
                    },
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
                    log(f"upload_missing_image_variant path={p}")
                    return False

            log(
                f"upload_image_prepare asset={asset} "
                f"fullhd_size={os.path.getsize(fullhd)} "
                f"mobile_size={os.path.getsize(mobile)} "
                f"thumb_size={os.path.getsize(thumb)}"
            )

            with open(fullhd, "rb") as fh_fullhd, \
                 open(mobile, "rb") as fh_mobile, \
                 open(thumb, "rb") as fh_thumb:

                files = {
                    "fullhd": ("fullhd.jpg", fh_fullhd, "image/jpeg"),
                    "mobile": ("mobile.jpg", fh_mobile, "image/jpeg"),
                    "thumb": ("thumb.jpg", fh_thumb, "image/jpeg"),
                }

                r = requests.post(
                    url,
                    headers=headers,
                    data={
                        "date": date,
                        "asset": asset,
                        "publish_last": "1" if publish_last else "0",
                    },
                    files=files,
                    timeout=(HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT),
                    verify=HTTP_VERIFY_SSL,
                )

    except requests.RequestException as e:
        log(f"upload_request_exception {asset} error={e}")
        return False
    except Exception as e:
        log(f"upload_prepare_exception {asset} error={e}")
        return False

    if r.status_code != 200:
        body = (r.text or "")[:1000].replace("\n", " ").replace("\r", " ")
        log(f"upload_http_error {r.status_code} asset={asset} body={body}")

        # optional: retry_after_seconds aus API auswerten
        try:
            j = r.json()
            retry_after = j.get("retry_after_seconds")
            if retry_after is not None:
                log(f"upload_retry_after_hint {retry_after}")
        except Exception:
            pass

        return False

    try:
        j = r.json()
    except Exception:
        log(f"invalid_json asset={asset} body={(r.text or '')[:500]}")
        return False

    if j.get("ok") is not True:
        log(f"upload_not_ok asset={asset} body={str(j)[:1000]}")
        return False

    log(f"upload_ok asset={asset}")
    return True

# -----------------------------------------------------------
# Asset Scan
# -----------------------------------------------------------
def _collect(date):
    base=os.path.join(config.ALLSKY_PATH,config.IMAGE_BASE_PATH)

    keo=_latest([
        os.path.join(base,date,"keogram",f"keogram-{date}.jpg"),
        os.path.join(base,date,"keogram",f"keogram-{date}.png"),
    ])

    st=_latest([
        os.path.join(base,date,"startrails",f"startrails-{date}.jpg"),
        os.path.join(base,date,"startrails",f"startrails-{date}.png"),
    ])

    mp4=os.path.join(base,date,f"allsky-{date}.mp4")
    assets=[]

    if keo:
        assets.append(("keogram",keo))

    if st:
        assets.append(("startrail",st))

    if os.path.isfile(mp4):
        assets.append(("video",mp4))

    return assets

# -----------------------------------------------------------
# Jitter
# -----------------------------------------------------------
def _apply_jitter(date):
    window = int(getattr(config, "NIGHTLY_UPLOAD_JITTER_MAX_SECONDS", 3600))
    if window <= 0:
        log("jitter_seconds=0")
        return

    kamera = getattr(config, "KAMERA_ID", "ASK000")
    seed = f"{kamera}|{date}".encode()
    slot = int(hashlib.sha256(seed).hexdigest()[:8], 16) % window
    log(f"jitter_seconds={slot}")
    time.sleep(slot)
    
# -----------------------------------------------------------
# Main
# -----------------------------------------------------------
def upload_nightly_batch(date=None):
    if date is None:
        date=(datetime.now()-timedelta(days=1)).strftime("%Y%m%d")

    log(f"nightly_start {date}")

    assets=_collect(date)

    if not assets:
        log("no_assets")
        return False

    prepared=[]

    # ---------------------------------------------------
    # Phase 1: vorbereiten (CPU)
    # ---------------------------------------------------
    for asset,path in assets:

        log(f"prepare {asset}")

        if not _file_ready(path):
            log("file_not_ready")
            continue

        tmp=tempfile.mkdtemp(prefix=f"nightly_{asset}_")

        try:

            if asset in ("keogram","startrail"):

                variants=_create_three(path,tmp)

                prepared.append(
                    dict(asset=asset,files=variants,tmp=tmp)
                )

            elif asset=="video":

                video,thumb=_prepare_video(path,tmp)

                prepared.append(
                    dict(asset=asset,files=(video,thumb),tmp=tmp)
                )

        except Exception as e:

            log(f"prepare_failed {e}")

    if not prepared:
        log("nothing_prepared")
        return False

    # ---------------------------------------------------
    # Phase 2: Jitter warten
    # ---------------------------------------------------
    _apply_jitter(date)

    # ---------------------------------------------------
    # Phase 3: Upload
    # ---------------------------------------------------
    for job in prepared:

        asset=job["asset"]
        files=job["files"]

        attempt=0
        ok = False

        for attempt in range(1, UPLOAD_MAX_RETRIES + 1):
            log(f"upload {asset} attempt={attempt}/{UPLOAD_MAX_RETRIES}")

            if _upload(asset, date, files, True):
                ok = True
                break

            if attempt < UPLOAD_MAX_RETRIES:
                delay = random.randint(
                    UPLOAD_RETRY_MIN_SECONDS,
                    UPLOAD_RETRY_MAX_SECONDS
                )
                log(f"retry_in {delay}")
                time.sleep(delay)

        if not ok:
            log(f"upload_failed {asset}")

        # temp löschen
        shutil.rmtree(job["tmp"],ignore_errors=True)

    log("nightly_done")

    return True