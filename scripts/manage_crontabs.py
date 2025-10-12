#!/usr/bin/env python3
import subprocess
import tempfile
import os
from askutils import config
from askutils.utils.logger import log, warn

def get_existing_crontab() -> str:
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        return ""
    return result.stdout

def write_new_crontab(new_content: str):
    with tempfile.NamedTemporaryFile(delete=False, mode="w") as temp:
        temp.write(new_content)
        temp_path = temp.name
    subprocess.run(["crontab", temp_path])
    os.unlink(temp_path)

def update_crontab():
    existing_lines = get_existing_crontab().splitlines()
    filtered = []

    # Entferne alte AUTOCRON-Eintraege und alle zugehoerigen Kommandozeilen
    skip_next = False
    for line in existing_lines:
        stripped = line.strip()
        if skip_next:
            skip_next = False
            continue
        # Kommentare der Form '# AUTOCRON: ...'
        if stripped.startswith('# AUTOCRON:'):
            skip_next = True
            continue
        # Cron-Zeilen, die einen unserer Jobs aus config.CRONTABS enthalten
        if any(job['command'] in stripped for job in config.CRONTABS):
            continue
        filtered.append(line)

    # Füge nun aktuelle CRONTABS hinzu
    for job in config.CRONTABS:
        comment = f"# AUTOCRON: {job['comment']}"
        entry = f"{job['schedule']} {job['command']}"
        filtered.append(comment)
        filtered.append(entry)

    new_crontab = "\n".join(filtered) + "\n"
    write_new_crontab(new_crontab)
    log("Crontab wurde aktualisiert.")

if __name__ == "__main__":
    update_crontab()
