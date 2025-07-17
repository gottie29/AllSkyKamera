#!/bin/bash

# Marker, der in den Cron-Einträgen vorkommt
CRON_MARKER="AllSkyKamera"

# 1) Versuch: Verzeichnis, in dem dieses Script liegt (wenn das Script im Installations-Verzeichnis abgelegt ist)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 2) Fallback: aus dem ersten gefundenen Cron-Eintrag ableiten
if crontab -l &>/dev/null; then
  CRON_LINE=$(crontab -l | grep "$CRON_MARKER" | head -n1)
  if [[ $CRON_LINE =~ ([^[:space:]]+/AllSkyKamera)(/[^[:space:]]+)? ]]; then
    CRON_PATH="${BASH_REMATCH[1]}"
    CRON_DIR="$(dirname "$CRON_PATH")"
  fi
fi

# Entscheide, welches Verzeichnis wir nehmen
if [ -d "$SCRIPT_DIR/AllSkyKamera" ]; then
  INSTALL_DIR="$SCRIPT_DIR/AllSkyKamera"
elif [ -d "$SCRIPT_DIR" ] && [[ "$(basename "$SCRIPT_DIR")" == "AllSkyKamera" ]]; then
  INSTALL_DIR="$SCRIPT_DIR"
elif [ -n "$CRON_DIR" ] && [ -d "$CRON_DIR" ]; then
  INSTALL_DIR="$CRON_DIR"
else
  echo "⚠️ Konnte Installationsverzeichnis nicht automatisch ermitteln."
  echo "Bitte Pfad manuell eingeben (z.B. /home/pi/AllSkyKamera):"
  read -r INSTALL_DIR
fi

echo "Gefundenes Installations-Verzeichnis: $INSTALL_DIR"
echo "Achtung: Mit diesem Skript werden alle automatisch angelegten Crontabs"
echo "mit dem Marker '$CRON_MARKER' entfernt und das Verzeichnis"
echo "'$INSTALL_DIR' unwiderruflich gelöscht."
read -p "Wirklich alle Daten löschen? [y/N] " answer

case "$answer" in
  [Yy])
    # Cron-Einträge mit Marker entfernen
    if crontab -l &>/dev/null; then
      crontab -l | grep -v "$CRON_MARKER" | crontab -
      echo "→ Cron-Einträge mit '$CRON_MARKER' wurden entfernt."
    else
      echo "→ Keine Crontab gefunden oder leer."
    fi

    # Verzeichnis löschen
    if [ -d "$INSTALL_DIR" ]; then
      rm -rf "$INSTALL_DIR"
      echo "→ Verzeichnis '$INSTALL_DIR' wurde gelöscht."
    else
      echo "→ Verzeichnis '$INSTALL_DIR' existiert nicht."
    fi

    echo "Deinstallation abgeschlossen."
    ;;
  *)
    echo "Abbruch: Es wurde nichts gelöscht."
    ;;
esac
