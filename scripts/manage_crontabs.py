#!/usr/bin/env python3
import subprocess
import tempfile
import os
from askutils import config
from askutils.utils.logger import log, warn

def get_existing_crontab():
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        return ""
    return result.stdout

def write_new_crontab(new_content):
    with tempfile.NamedTemporaryFile(delete=False, mode="w") as temp:
        temp.write(new_content)
        temp_path = temp.name
    subprocess.run(["crontab", temp_path])
    os.unlink(temp_path)

def update_crontab():
    existing = get_existing_crontab().splitlines()
    updated = []
    existing_comments = set()

    for line in existing:
        if line.strip().startswith("# AUTOCRON:"):
            # merken, welche AutoCron-Kommentare schon da waren
            existing_comments.add(line.strip())
            continue
        if not any(c in line for c in ["python3 -m scripts.raspi_status"]):  # ggf. anpassen
            updated.append(line)

    # Nun alle neuen definieren
    for job in config.CRONTABS:
        comment_line = f"# AUTOCRON: {job['comment']}"
        cmd_line = f"{job['schedule']} {job['command']}"
        updated.append(comment_line)
        updated.append(cmd_line)

    write_new_crontab("\n".join(updated) + "\n")
    log("✅ Crontab wurde aktualisiert.")

if __name__ == "__main__":
    update_crontab()
