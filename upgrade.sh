#!/usr/bin/env bash
# Datei: check_remote_version.sh
# Vergleicht lokale version-Datei mit der im GitHub-Repo

PROJECT_DIR="$HOME/AllSkyKamera"
VERSION_FILE="$PROJECT_DIR/version"
REMOTE_URL="https://raw.githubusercontent.com/gottie29/AllSkyKamera/main/version"

# Lokale Version
if [ -f "$VERSION_FILE" ]; then
    LOCAL_VER=$(head -n1 "$VERSION_FILE" | tr -d ' \t\r\n')
else
    echo "❌ Keine lokale Versionsdatei gefunden!"
    exit 1
fi

# Remote-Version von GitHub laden
REMOTE_VER=$(curl -fsSL "$REMOTE_URL" | head -n1 | tr -d ' \t\r\n')

if [ -z "$REMOTE_VER" ]; then
    echo "❌ Konnte Remote-Version nicht abrufen!"
    exit 1
fi

# Vergleich
echo "Lokale Version : $LOCAL_VER"
echo "Remote Version : $REMOTE_VER"

if [ "$LOCAL_VER" = "$REMOTE_VER" ]; then
    echo "✅ Versionen sind identisch"
else
    echo "⚠️  Versionen unterscheiden sich!"
fi
