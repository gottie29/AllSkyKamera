#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import urllib.request
from typing import Dict, Any


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOCAL_VERSION_PATH = os.path.join(PROJECT_ROOT, "version")

# HIER SPÄTER DEIN ECHTES RAW-GITHUB-ZIEL EINTRAGEN
GITHUB_VERSION_URL = "https://raw.githubusercontent.com/gottie29/AllSkyKamera/main/version"

SETUPUI_SERVICE_NAME = "allsky-setupui.service"


def read_text_file(path: str) -> str:
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def fetch_github_version(url: str = GITHUB_VERSION_URL, timeout: int = 8) -> str:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="replace").strip()
            return content
    except Exception:
        return ""


def normalize_version(value: str) -> str:
    return (value or "").strip()


def parse_version_parts(version: str):
    """
    Macht aus '2026-03-25' oder '1.2.3' eine vergleichbare Struktur.
    Fallback: reiner Stringvergleich, wenn nichts Sinnvolles erkannt wird.
    """
    v = normalize_version(version)

    if not v:
        return ("",)

    if "-" in v:
        parts = v.split("-")
        if all(p.isdigit() for p in parts):
            return tuple(int(p) for p in parts)

    if "." in v:
        parts = v.split(".")
        if all(p.isdigit() for p in parts):
            return tuple(int(p) for p in parts)

    return (v,)


def is_github_newer(local_version: str, github_version: str) -> bool:
    local_v = normalize_version(local_version)
    github_v = normalize_version(github_version)

    if not github_v:
        return False
    if not local_v:
        return True

    try:
        return parse_version_parts(github_v) > parse_version_parts(local_v)
    except Exception:
        return github_v != local_v


def get_version_status() -> Dict[str, Any]:
    local_version = read_text_file(LOCAL_VERSION_PATH)
    github_version = fetch_github_version()

    return {
        "local_version": local_version or "–",
        "github_version": github_version or "–",
        "github_reachable": bool(github_version),
        "update_available": is_github_newer(local_version, github_version),
        "local_version_path": LOCAL_VERSION_PATH,
        "github_version_url": GITHUB_VERSION_URL,
    }


def run_update() -> Dict[str, Any]:
    """
    Führt das Update aus:
    - git pull im Projektverzeichnis
    - danach Restart des SetupUI-Service
    """
    result = {
        "ok": False,
        "steps": [],
        "error": "",
    }

    try:
        cmd = ["git", "-C", PROJECT_ROOT, "pull"]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )

        result["steps"].append({
            "command": " ".join(cmd),
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        })

        if proc.returncode != 0:
            result["error"] = "git pull fehlgeschlagen"
            return result

        restart_cmd = ["sudo", "systemctl", "restart", SETUPUI_SERVICE_NAME]
        proc2 = subprocess.run(
            restart_cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        result["steps"].append({
            "command": " ".join(restart_cmd),
            "returncode": proc2.returncode,
            "stdout": proc2.stdout.strip(),
            "stderr": proc2.stderr.strip(),
        })

        if proc2.returncode != 0:
            result["error"] = "Restart des SetupUI-Service fehlgeschlagen"
            return result

        result["ok"] = True
        return result

    except Exception as e:
        result["error"] = str(e)
        return result