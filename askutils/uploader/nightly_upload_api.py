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
VIDEO_CRF = 24
VIDEO_PRESET = "veryfast"
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
        "-c:a","aac","-b:a","128k",
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

def _prepare_video(src,tmp):
    ext=os.path.splitext(src)[1]
    v=os.path.join(tmp,"video"+ext)
    t=os.path.join(tmp,"thumb.jpg")

    _reduce_video(src,v)
    _video_thumb(v,t)

    return v,t

# -----------------------------------------------------------
# Upload
# -----------------------------------------------------------
def _upload(asset,date,datafiles,publish_last):
    url=_get_api_url()
    headers={"X-API-Key":API_KEY}
    files={}

    if asset=="video":
        v,t=datafiles
        files={
            "file":(os.path.basename(v),open(v,"rb"),"video/mp4"),
            "thumb":("thumb.jpg",open(t,"rb"),"image/jpeg")
        }
    else:
        files={
            "fullhd":("fullhd.jpg",open(datafiles["fullhd"],"rb"),"image/jpeg"),
            "mobile":("mobile.jpg",open(datafiles["mobile"],"rb"),"image/jpeg"),
            "thumb":("thumb.jpg",open(datafiles["thumb"],"rb"),"image/jpeg")
        }

    r=requests.post(
        url,
        headers=headers,
        data={
            "date":date,
            "asset":asset,
            "publish_last":"1" if publish_last else "0"
        },
        files=files,
        timeout=(HTTP_CONNECT_TIMEOUT,HTTP_READ_TIMEOUT),
        verify=HTTP_VERIFY_SSL
    )

    if r.status_code!=200:
        log(f"upload_http_error {r.status_code}")
        return False

    try:
        j=r.json()
    except:
        log("invalid_json")
        return False

    return j.get("ok")==True

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

    window=int(getattr(config,"NIGHTLY_UPLOAD_JITTER_MAX_SECONDS",10))
    kamera=getattr(config,"KAMERA_ID","ASK000")
    seed=f"{kamera}|{date}".encode()
    slot=int(hashlib.sha256(seed).hexdigest()[:8],16)%window
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
        ok=False

        while attempt<=UPLOAD_MAX_RETRIES:

            attempt+=1

            log(f"upload {asset} attempt={attempt}")

            if _upload(asset,date,files,True):

                ok=True
                break

            if attempt<=UPLOAD_MAX_RETRIES:

                delay=random.randint(
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