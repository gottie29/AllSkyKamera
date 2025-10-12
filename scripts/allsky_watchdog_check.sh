sudo tee /usr/local/bin/allsky_watchdog_check.sh > /dev/null << 'EOF'
#!/bin/bash
TMP_IMG="/home/pi/allsky/tmp/image.jpg"
NET_HOST="8.8.8.8"
NET_TIMEOUT=5
MAX_AGE=$((30*60))           # 30 Minuten in Sekunden
STATE_DIR="/var/run/allsky"
LAST_OK="$STATE_DIR/net_last_ok"

mkdir -p "$STATE_DIR"

now=$(date +%s)

# 1) Bild-Alter pruefen
if [ ! -e "$TMP_IMG" ] || [ $(( now - $(stat -c %Y "$TMP_IMG") )) -gt $MAX_AGE ]; then
  exit 1
fi

# 2) Netz-Check
if ping -c1 -W"$NET_TIMEOUT" "$NET_HOST" &>/dev/null; then
  # Netzwerk OK -> Zeitstempel zuruecksetzen
  rm -f "$LAST_OK"
else
  # Netzwerk down -> alterstempel setzen/auslesen
  if [ ! -f "$LAST_OK" ]; then
    echo "$now" > "$LAST_OK"
    exit 0
  fi
  down_since=$(cat "$LAST_OK")
  if [ $(( now - down_since )) -gt $MAX_AGE ]; then
    # laenger als 30 Minuten down -> Reboot
    exit 1
  fi
fi

exit 0
EOF

sudo chmod +x /usr/local/bin/allsky_watchdog_check.sh

