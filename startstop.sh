#!/usr/bin/env bash
# Entfernt versehentliche CRLF-Zeilenenden bei Aufruf
if command -v dos2unix &>/dev/null; then
    dos2unix "$0" &>/dev/null || true
else
    sed -i 's/\r$//' "$0" || true
fi

set -euo pipefail

# Muss im Projekt-Root (mit askutils/) ausgefuehrt werden.
if [ ! -d "askutils" ]; then
    echo "❌ Dieses Skript muss im Projekt-Roo 'AllSkyKamera' (mit askutils/) aufgerufen werden."
    exit 1
fi

PROJECT_ROOT="$(pwd)"
echo "Arbeitsverzeichnis: $PROJECT_ROOT"

CONFIG="$PROJECT_ROOT/askutils/config.py"
CONFIG_STOP="$PROJECT_ROOT/askutils/config_stop.py"

# --- Parameter pruefen ---
if [ $# -ne 1 ]; then
    echo "Nutzung: $0 [start|stop]"
    exit 1
fi

case "$1" in
    stop)
        if [ -f "$CONFIG" ]; then
            mv "$CONFIG" "$CONFIG_STOP"
            echo "config.py wurde in config_stop.py umbenannt."
        else
            echo "config.py existiert nicht (evtl. schon gestoppt?)."
        fi
        ;;
    start)
        if [ -f "$CONFIG_STOP" ]; then
            mv "$CONFIG_STOP" "$CONFIG"
            echo "config_stop.py wurde in config.py umbenannt."
        else
            echo "config_stop.py existiert nicht (evtl. schon gestartet?)."
        fi
        ;;
    *)
        echo "❌ Ungueltiger Parameter: $1"
        echo "Nutzung: $0 [start|stop]"
        exit 1
        ;;
esac
