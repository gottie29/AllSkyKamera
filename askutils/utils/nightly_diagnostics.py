"""Kompakte, fehlertolerante JSONL-Diagnose für Nightly-Uploads.

Die Logs bleiben zunächst lokal. Ein getrennter Uploader wird später ergänzt.
Keine API-Keys, Tokens oder vollständigen HTTP-Antworten erfassen.
"""
import json
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

_ACTIVE = None
_MAX_BYTES = 256 * 1024
_MAX_DETAILS = 350
# Nicht alle Konsolenmeldungen kopieren: Nur strukturierte Diagnoseereignisse.
_EVENT_PREFIXES = (
    'nightly_', 'collect_', 'asset_', 'prepare_', 'file_',
    'video_', 'upload_', 'retry_', 'jitter_', 'primary_base',
    'indi_', 'no_assets', 'nothing_prepared', 'invalid_json',
)


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def _safe_text(value):
    text = str(value).replace('\r', ' ').replace('\n', ' ')
    # Keine URL-Querystrings/Secrets mitprotokollieren.
    text = re.sub(r'(?i)(api[_-]?key|token|authorization|password|secret)=\S+', r'\1=[REDACTED]', text)
    return text[:_MAX_DETAILS]


def _event(event, **fields):
    state = _ACTIVE
    if not state or state['overflow']:
        return
    payload = {
        'ts': _utc_now(),
        'run_id': state['run_id'],
        'camera': state['camera'],
        'night': state['night'],
        'event': event,
    }
    payload.update(fields)
    try:
        line = (json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
        if state['bytes'] + len(line) > _MAX_BYTES:
            state['overflow'] = True
            return
        with state['path'].open('ab') as handle:
            handle.write(line)
        state['bytes'] += len(line)
    except OSError:
        # Diagnose darf den Upload niemals abbrechen.
        pass


def begin(night, camera, version):
    global _ACTIVE
    _ACTIVE = None
    camera = str(camera)
    night = str(night)
    if not re.fullmatch(r'ASK\d{3}', camera) or not re.fullmatch(r'\d{8}', night):
        return
    try:
        folder = Path.home() / 'AllSkyKamera' / 'logs' / 'nightly' / 'pending'
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        backlog = sum(p.stat().st_size for p in folder.iterdir()
                      if p.is_file() and (p.name.endswith('.jsonl') or p.name.endswith('.jsonl.tmp')))
        if backlog >= 20 * 1024 * 1024:
            print('WARNUNG nightly_diagnostics: 20 MiB Log-Rueckstau; neues Log ausgesetzt', flush=True)
            return
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
        suffix = secrets.token_hex(4)
        filename = f'{camera}_{night}_{stamp}_{suffix}.jsonl'
        path = folder / (filename + '.tmp')
        with path.open('xb'):
            pass
        _ACTIVE = dict(camera=camera, night=night, run_id=suffix,
                       path=path, bytes=0, overflow=False, start=time.monotonic())
        # config.VERSION ist nicht in jeder Kamerakonfiguration vorhanden.
        version_file = Path.home() / 'AllSkyKamera' / 'version'
        try:
            version = version_file.read_text(encoding='utf-8').strip() or version
        except OSError:
            pass
        _event('run_start', version=_safe_text(version), pid=os.getpid())
    except OSError:
        _ACTIVE = None


def record_message(message):
    msg = str(message)
    event = msg.split(' ', 1)[0].split('=', 1)[0]
    if event != 'upload' and not event.startswith(_EVENT_PREFIXES):
        return
    if event == 'upload' and 'attempt=' in msg:
        match = re.search(r'asset=(\w+)\s+attempt=(\d+)/(\d+)', msg)
        if match and _ACTIVE:
            _ACTIVE['asset'] = match.group(1)
            _ACTIVE['attempt'] = int(match.group(2))
    if _ACTIVE:
        if event in ('no_assets', 'nothing_prepared'):
            _ACTIVE['final_status'] = event
        # Nur ENDGUELTIGE Fehler werten: Einzelversuche duerfen fehlschlagen
        # und bei einer spaeteren Wiederholung dennoch erfolgreich sein.
        if event in ('upload_ok', 'upload_failed', 'prepare_failed'):
            match = re.search(r'asset=(\w+)', msg)
            if match:
                asset_name = match.group(1)
                key = ('successful_assets' if event == 'upload_ok'
                       else 'failed_assets')
                _ACTIVE.setdefault(key, set()).add(asset_name)
                if event == 'prepare_failed':
                    _ACTIVE['has_prepare_failure'] = True
    _event('trace', step=event, details=_safe_text(msg))


def timed_post(*args, **kwargs):
    """Zeitmessung, sonst identischer requests.post-Aufruf."""
    start = time.monotonic()
    state = _ACTIVE or {}
    asset = str(kwargs.get('data', {}).get('asset', state.get('asset', 'unknown')))
    attempt = state.get('attempt')
    file_size = None
    try:
        parts = kwargs.get('files', {})
        primary = parts.get('file') if asset == 'video' else parts.get('fullhd')
        if primary is not None:
            handle = primary[1]
            file_size = os.fstat(handle.fileno()).st_size
    except (OSError, AttributeError, IndexError, TypeError):
        pass
    meta = dict(asset=asset, attempt=attempt, size_bytes=file_size)
    _event('http_post_start', request_timeout=list(kwargs.get('timeout', ())), **meta)
    try:
        response = requests.post(*args, **kwargs)
        _event('http_post_end', duration_ms=round((time.monotonic()-start)*1000),
               http_status=response.status_code, **meta)
        return response
    except Exception as exc:
        _event('http_post_exception', duration_ms=round((time.monotonic()-start)*1000),
               exception_type=type(exc).__name__, details=_safe_text(exc), **meta)
        raise


def finish(status, error_type=None):
    global _ACTIVE
    state = _ACTIVE
    if not state:
        return
    successes = state.get('successful_assets', set())
    failures = state.get('failed_assets', set()) - successes
    if status != 'aborted':
        if failures and successes:
            status = 'partial_success'
        elif failures:
            status = ('prepare_failed' if state.get('has_prepare_failure')
                      else 'upload_failed')
        elif status == 'failed':
            status = state.get('final_status', status)
    _event('run_end', status=status, error_type=error_type,
           duration_ms=round((time.monotonic()-state['start'])*1000),
           truncated=state['overflow'])
    try:
        final = state['path'].with_suffix('')  # entfernt nur .tmp
        state['path'].rename(final)
    except OSError:
        pass
    _ACTIVE = None
