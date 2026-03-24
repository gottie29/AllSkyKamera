#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import os
import random
import time

import requests

from askutils import config

try:
    from askutils.ASKsecret import API_KEY
except Exception:
    API_KEY = None


_DEFAULT_ENC_METEOR_UPLOAD_API_URL = (
    "aHR0cHM6Ly9hbGxza3lrYW1lcmEuc3BhY2UvYXBpL3YxL21ldGVvcl91cGxvYWQucGhw"
)

HTTP_CONNECT_TIMEOUT = 20
HTTP_READ_TIMEOUT = 180
HTTP_VERIFY_SSL = True


def log(msg):
    print(msg, flush=True)


def _get_api_url():
    return base64.b64decode(_DEFAULT_ENC_METEOR_UPLOAD_API_URL).decode().strip()


def _get_kamera_id():
    return str(getattr(config, "KAMERA_ID", None) or getattr(config, "KAMERA", None) or "")


def _apply_upload_jitter():
    max_s = getattr(config, "METEOR_UPLOAD_JITTER_MAX_SECONDS", 90)
    try:
        max_s = int(max_s)
    except Exception:
        max_s = 90

    if max_s <= 0:
        return

    delay = random.randint(0, max_s)
    if delay > 0:
        log("Meteor-Upload Jitter: warte %ss ..." % delay)
        time.sleep(delay)


def _candidate_paths(day_dir, candidate_id):
    candidate_dir = os.path.join(day_dir, candidate_id)
    return {
        "candidate_dir": candidate_dir,
        "candidate_json": os.path.join(candidate_dir, "candidate.json"),
        "current_fullhd": os.path.join(candidate_dir, "current_fullhd.jpg"),
        "current_small": os.path.join(candidate_dir, "current_small.jpg"),
        "previous_small": os.path.join(candidate_dir, "previous_small.jpg"),
        "diff_small": os.path.join(candidate_dir, "diff_small.jpg"),
        "boxed_small": os.path.join(candidate_dir, "boxed_small.jpg"),
        "uploaded_ok": os.path.join(candidate_dir, "uploaded.ok"),
        "day_index": os.path.join(day_dir, "index.json"),
    }


def _upload_candidate(day_dir_name, day_dir, candidate_id):
    paths = _candidate_paths(day_dir, candidate_id)

    if os.path.isfile(paths["uploaded_ok"]):
        return False

    if not API_KEY:
        log("Meteor-Upload: API_KEY fehlt.")
        return False

    required = [
        paths["candidate_json"],
        paths["current_fullhd"],
        paths["current_small"],
        paths["previous_small"],
        paths["diff_small"],
        paths["boxed_small"],
    ]

    for path in required:
        if not os.path.isfile(path):
            log("Meteor-Upload: Datei fehlt: %s" % path)
            return False

    url = _get_api_url()
    headers = {
        "X-API-Key": API_KEY
    }

    data = {
        "kamera": _get_kamera_id(),
        "asset": "meteor",
        "day": day_dir_name,
        "candidate_id": candidate_id,
    }

    try:
        with open(paths["candidate_json"], "rb") as f_json, \
             open(paths["current_fullhd"], "rb") as f_fullhd, \
             open(paths["current_small"], "rb") as f_small, \
             open(paths["previous_small"], "rb") as f_prev, \
             open(paths["diff_small"], "rb") as f_diff, \
             open(paths["boxed_small"], "rb") as f_boxed, \
             open(paths["day_index"], "rb") as f_index:

            files = {
                "candidate_json": ("candidate.json", f_json, "application/json"),
                "current_fullhd": ("current_fullhd.jpg", f_fullhd, "image/jpeg"),
                "current_small": ("current_small.jpg", f_small, "image/jpeg"),
                "previous_small": ("previous_small.jpg", f_prev, "image/jpeg"),
                "diff_small": ("diff_small.jpg", f_diff, "image/jpeg"),
                "boxed_small": ("boxed_small.jpg", f_boxed, "image/jpeg"),
                "day_index": ("index.json", f_index, "application/json"),
            }

            response = requests.post(
                url,
                headers=headers,
                data=data,
                files=files,
                timeout=(HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT),
                verify=HTTP_VERIFY_SSL,
            )

    except requests.RequestException as e:
        log("Meteor-Upload fehlgeschlagen (Request): %s" % str(e))
        return False
    except Exception as e:
        log("Meteor-Upload fehlgeschlagen (Prepare): %s" % str(e))
        return False

    if response.status_code != 200:
        body = (response.text or "")[:1000].replace("\n", " ").replace("\r", " ")
        log("Meteor-Upload HTTP-Fehler %s: %s" % (response.status_code, body))
        return False

    try:
        result = response.json()
    except Exception:
        log("Meteor-Upload: API antwortet nicht mit JSON: %s" % ((response.text or "")[:500]))
        return False

    if result.get("ok") is not True:
        log("Meteor-Upload: API meldet Fehler: %s" % str(result)[:1000])
        return False

    log("Meteor-Upload erfolgreich: %s" % candidate_id)
    return True


def upload_pending_meteor_candidates(day_dir_name, day_dir):
    _apply_upload_jitter()

    uploaded_ids = []

    if not os.path.isdir(day_dir):
        return uploaded_ids

    for name in sorted(os.listdir(day_dir)):
        candidate_dir = os.path.join(day_dir, name)
        if not os.path.isdir(candidate_dir):
            continue
        if name == "quicklook":
            continue

        candidate_json = os.path.join(candidate_dir, "candidate.json")
        uploaded_ok = os.path.join(candidate_dir, "uploaded.ok")

        if not os.path.isfile(candidate_json):
            continue
        if os.path.isfile(uploaded_ok):
            continue

        ok = _upload_candidate(day_dir_name, day_dir, name)
        if ok:
            uploaded_ids.append(name)

    return uploaded_ids