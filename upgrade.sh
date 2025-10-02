#!/usr/bin/env bash
# Datei: ask_version.sh
# Liest die aktuelle Versionsnummer aus AllSkyKamera/version

PROJECT_DIR="$HOME/AllSkyKamera"
VERSION_FILE="$PROJECT_DIR/version"

if [ -f "$VERSION_FILE" ]; then
    VERSION=$(head -n1 "$VERSION_FILE" | tr -d ' \t\r\n')
    echo "Aktuelle Version: $VERSION"
else
    echo "⚠️  Keine Versionsdatei gefunden unter: $VERSION_FILE"
    exit 1
fi
