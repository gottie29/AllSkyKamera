#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from typing import Any, Dict, Optional

from askutils import config
from askutils import ASKsecret

def _api_key() -> str:
    return ASKsecret.API_KEY


def _api_url() -> str:
    # entweder direkt aus ASKsecret
    if hasattr(ASKsecret, "API_URL"):
        return ASKsecret.API_URL

    # oder fallback, falls du es später umbenennst
    if hasattr(ASKsecret, "SERVER_CONTROL_API_URL"):
        return ASKsecret.SERVER_CONTROL_API_URL

    raise RuntimeError("No API URL found in ASKsecret.py")


def _cfg(key: str, default: Any = None) -> Any:
    return getattr(config, key, default)


def _api_url() -> str:
    # Default passend zu deinem Server
    return str(_cfg("SERVER_CONTROL_API_URL", "https://allskykamera.space/api/v1/control.php"))

def _http_get_json(url: str, api_key: str) -> Dict[str, Any]:
    req = urllib.request.Request(url, method="GET", headers={"X-API-KEY": api_key})
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw)


def _http_post_json(url: str, api_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        method="POST",
        data=data,
        headers={
            "X-API-KEY": api_key,
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw)


def _run_upload_tmpimages_range(date: str, start: str, end: str) -> subprocess.CompletedProcess[str]:
    # ruft dein bestehendes Modul auf
    cmd = ["python3", "-m", "scripts.run_tmpimages_upload", date, start, end]
    return subprocess.run(
        cmd,
        cwd="/home/pi/AllSkyKamera",
        capture_output=True,
        text=True,
        timeout=3 * 60 * 60,  # 3h
    )


def poll_once() -> int:
    """
    1x abfragen, max. 1 Job bearbeiten, Ergebnis reporten.
    Rückgabecode:
      0 = ok / kein Job
      2 = Job fehlgeschlagen oder Report fehlgeschlagen
    """
    api_key = _api_key()
    if not api_key:
        print("[control_poll] Missing API key in config (API_KEY / X_API_KEY / CONTROL_API_KEY).")
        return 2

    url = _api_url()

    try:
        data = _http_get_json(url, api_key)
    except Exception as e:
        print(f"[control_poll] GET failed: {e}")
        return 2

    if data.get("status") != "ok":
        # z.B. {status:"no_job"} -> ok
        return 0

    job = data.get("job") or {}
    job_id = str(job.get("id") or "")
    job_type = str(job.get("type") or "")
    params = job.get("params") or {}

    ok = False
    exit_code = 1
    stdout = ""
    stderr = ""

    try:
        if job_type == "upload_tmpimages_range":
            date = str(params.get("date") or "")
            start = str(params.get("start") or "")
            end = str(params.get("end") or "")
            cp = _run_upload_tmpimages_range(date, start, end)
            exit_code = int(cp.returncode)
            stdout = cp.stdout or ""
            stderr = cp.stderr or ""
            ok = (exit_code == 0)
        else:
            ok = False
            exit_code = 3
            stderr = f"Unknown job type: {job_type}"
    except subprocess.TimeoutExpired:
        ok = False
        exit_code = 124
        stderr = "Command timed out"
    except Exception as e:
        ok = False
        exit_code = 1
        stderr = f"Exception: {e}"

    # Report back (Log begrenzen, damit POST nicht riesig wird)
    def cut(s: str, maxlen: int = 50000) -> str:
        if len(s) <= maxlen:
            return s
        return s[:maxlen] + "\n[truncated]"

    try:
        _http_post_json(
            url,
            api_key,
            {
                "id": job_id,
                "ok": ok,
                "exit_code": exit_code,
                "stdout": cut(stdout),
                "stderr": cut(stderr),
            },
        )
    except Exception as e:
        print(f"[control_poll] POST report failed: {e}")
        return 2

    return 0 if ok else 2


def main() -> int:
    return poll_once()


if __name__ == "__main__":
    sys.exit(main())
