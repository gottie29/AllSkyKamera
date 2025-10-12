#!/bin/bash

# Marker, der in den Cron-Eintraegen vorkommt
CRON_MARKER="AllSkyKamera"

# 1) Versuch: Verzeichnis, in dem dieses Script liegt
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
  echo "Konnte Installationsverzeichnis nicht automatisch ermitteln."
  echo "Bitte Pfad manuell eingeben (z.B. /home/pi/AllSkyKamera):"
  read -r INSTALL_DIR
fi

echo "Gefundenes Installations-Verzeichnis: $INSTALL_DIR"
echo "Achtung: Mit diesem Skript werden alle automatisch angelegten Crontabs"
echo "mit dem Marker '$CRON_MARKER' und alle '# AUTOCRON:'-Kommentare entfernt,"
echo "und das Verzeichnis '$INSTALL_DIR' unwiderruflich geloescht."
read -p "Wirklich alle Daten loeschen? [y/N] " answer

case "$answer" in
  [Yy])
    # Cron-Eintraege und AUTOCRON-Kommentare entfernen
    if crontab -l &>/dev/null; then
      crontab -l \
        | grep -v -E "$CRON_MARKER|^# AUTOCRON:" \
        | crontab -
      echo "-> Cron-Eintraege mit '$CRON_MARKER' und alle '# AUTOCRON:'-Kommentare wurden entfernt."
    else
      echo "-> Keine Crontab gefunden oder leer."
    fi

    # Verzeichnis loeschen
    if [ -d "$INSTALL_DIR" ]; then
      rm -rf "$INSTALL_DIR"
      echo "-> Verzeichnis '$INSTALL_DIR' wurde geloescht."
    else
      echo "-> Verzeichnis '$INSTALL_DIR' existiert nicht."
    fi

    echo "Deinstallation abgeschlossen."
    cd
    ;;
  *)
    echo "Abbruch: Es wurde nichts geloescht."
    ;;
esac
