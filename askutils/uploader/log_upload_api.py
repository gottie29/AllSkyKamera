"""Kleiner, unabhängiger HTTPS-Versand abgeschlossener Nightly-JSONL-Logs.

Aufruf aus raspi_status; keine Änderung bestehender Statuswerte.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import requests
from askutils.ASKsecret import API_URL, API_KEY
from askutils import config

PENDING = Path.home() / 'AllSkyKamera/logs/nightly/pending'
MAX_FILES = 1
MAX_BYTES = 256 * 1024


def upload_pending_logs():
    if not PENDING.is_dir():
        return
    if not API_KEY:
        print('log_upload: API_KEY fehlt', flush=True)
        return
    try:
        lock = PENDING / '.log_upload.lock'
        with lock.open('a+b') as guard:
            try:
                fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            _upload_locked()
    except Exception as exc:
        print('log_upload: Transport nicht moeglich: '+type(exc).__name__, flush=True)


def _upload_locked():
    parts = urlsplit(API_URL)
    if parts.scheme != 'https' or not parts.netloc:
        print('log_upload: HTTPS API_URL fehlt', flush=True)
        return
    url = f'{parts.scheme}://{parts.netloc}/api/v1/log_upload.php'
    camera = str(getattr(config, 'KAMERA_ID', ''))
    logs = sorted(PENDING.glob('*.jsonl'), key=lambda p:p.stat().st_mtime)[:MAX_FILES]
    for path in logs:
        if not path.name.startswith(camera + '_'):
            print('log_upload: Kamera-ID passt nicht: '+path.name, flush=True)
            continue
        try:
            size = path.stat().st_size
            if not (0 < size <= MAX_BYTES):
                print('log_upload: ungueltige Groesse: '+path.name, flush=True)
                continue
            # JSONL lokal prüfen, erst dann übertragen.
            with path.open('r',encoding='utf-8') as stream:
                for line in stream:
                    if not isinstance(json.loads(line),dict):
                        raise ValueError('JSONL object erwartet')
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            with path.open('rb') as fh:
                response = requests.post(
                    url,
                    headers={'X-API-Key':API_KEY},
                    data={'filename':path.name},
                    files={'file':(path.name,fh,'application/x-ndjson')},
                    timeout=(10,20),verify=True)
            try:
                result = response.json()
            except ValueError:
                result = {}
            if (response.status_code == 200 and result.get('ok') is True
                and result.get('camera') == camera
                and result.get('filename') == path.name
                and result.get('size') == size
                and result.get('sha256') == checksum):
                # Log nie löschen, wenn Inhalt zwischen Lesen und Antwort wechselte.
                if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == checksum:
                    path.unlink()
                    print('log_upload: bestaetigt und lokal geloescht: '+path.name,flush=True)
            else:
                print('log_upload: Serverbestaetigung fehlt: '+path.name+' HTTP='+str(response.status_code),flush=True)
                break
        except (OSError, requests.RequestException, ValueError) as exc:
            print('log_upload: fehlgeschlagen: '+path.name+' '+type(exc).__name__,flush=True)
            break
