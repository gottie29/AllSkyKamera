#!/usr/bin/env python3
"""
manage_crontabs.py

Liest die aktuelle Crontab, entfernt alle alten AUTOCRON-Eintraege
und alle Zeilen, die zu den in config.CRONTABS definierten Jobs gehoeren,
und schreibt dann die aktuelle Liste aus config.CRONTABS wieder hinein.

Die Jobs werden mit Kommentaren der Form

    # AUTOCRON: <Kommentar>
    */5 * * * * cd /pfad/zur/AllSkyKamera && python3 -m scripts.irgendwas

eingetragen.
"""

import subprocess
import tempfile
import os

from askutils import config
from askutils.utils.logger import log, warn


def get_existing_crontab() -> str:
    """Aktuelle Crontab des Benutzers als String zurueckgeben.
    Wenn noch keine Crontab existiert, leere Zeichenkette zurueckgeben.
    """
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        warn("crontab-Kommando wurde nicht gefunden.")
        return ""

    if result.returncode != 0:
        # Typischer Fall: "no crontab for <user>"
        return ""

    return result.stdout


def write_new_crontab(new_content: str) -> None:
    """Neue Crontab aus einem String schreiben."""
    with tempfile.NamedTemporaryFile(delete=False, mode="w") as temp:
        temp.write(new_content)
        temp_path = temp.name

    try:
        subprocess.run(["crontab", temp_path], check=False)
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def update_crontab() -> None:
    """Crontab anhand von config.CRONTABS aktualisieren."""
    existing_lines = get_existing_crontab().splitlines()
    filtered: list[str] = []

    # Alle Kommandos, die wir verwalten (aus config.CRONTABS)
    managed_jobs = getattr(config, "CRONTABS", [])
    managed_commands = {job.get("command", "") for job in managed_jobs if job.get("command")}

    # 1) Alte AUTOCRON-Bloecke + Zeilen mit bekannten Kommandos entfernen
    skip_next = False
    for line in existing_lines:
        stripped = line.strip()

        # Naechste Zeile nach "# AUTOCRON:" ueberspringen (das ist die eigentliche Cronzeile)
        if skip_next:
            skip_next = False
            continue

        # Kommentare der Form "# AUTOCRON: ..."
        if stripped.startswith("# AUTOCRON:"):
            skip_next = True
            continue

        # Falls eine bestehende Cronzeile eines unserer bekannten Kommandos enthaelt,
        # wird sie entfernt, damit wir sie mit den aktuellen Werten neu hinzufuegen.
        if any(cmd and cmd in stripped for cmd in managed_commands):
            continue

        # Alle anderen Zeilen bleiben erhalten (inkl. manueller Jobs, PATH, MAILTO, etc.)
        filtered.append(line)

    # 2) Aktuelle CRONTABS aus config anhaengen (einheitlich unter AUTOCRON)
    seen_entries = set()
    for job in managed_jobs:
        comment = f"# AUTOCRON: {job.get('comment', 'Job')}"
        schedule = job.get("schedule", "").strip()
        command = job.get("command", "").strip()

        if not schedule or not command:
            # Ungueltiger Eintrag – wir loggen nur eine Warnung
            warn(f"Ungueltiger CRONTABS-Eintrag in config ignoriert: {job!r}")
            continue

        entry = f"{schedule} {command}"

        # Doppelte Eintraege vermeiden
        if entry in seen_entries:
            continue
        seen_entries.add(entry)

        filtered.append(comment)
        filtered.append(entry)

    # 3) Neue Crontab schreiben
    new_crontab = "\n".join(filtered).rstrip() + "\n"
    write_new_crontab(new_crontab)
    log("Crontab wurde aktualisiert.")


if __name__ == "__main__":
    update_crontab()
