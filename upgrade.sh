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
# 2. Version aus Git
if [ -d "$PROJECT_DIR/.git" ]; then
    cd "$PROJECT_DIR" || exit 1
    if git describe --tags --always --dirty >/dev/null 2>&1; then
        GIT_VERSION=$(git describe --tags --always --dirty)
        echo "Git-Version   : $GIT_VERSION"
    else
        GIT_COMMIT=$(git rev-parse --short HEAD)
        echo "Git-Commit    : $GIT_COMMIT"
    fi
else
    echo "Git-Version   : (kein Git-Repo)"
fi
