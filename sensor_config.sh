#!/usr/bin/env bash
# Datei: sensor_config.sh – interaktiver Editor fuer Sensor-Settings in askutils/config.py
# Anforderungen: bash, python3, awk, sed

set -euo pipefail
export LANG=C.UTF-8
export LC_ALL=C.UTF-8

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFG="$ROOT_DIR/askutils/config.py"

if [ ! -f "$CFG" ]; then
  echo "Fehler: Datei nicht gefunden: $CFG"
  echo "Bitte im Projekt-Root (mit askutils/config.py) ausfuehren."
  exit 1
fi

ts_now() { date +"%Y%m%d-%H%M%S"; }

backup_cfg() {
  local bak="$CFG.bak.$(ts_now)"
  cp "$CFG" "$bak"
  echo "Backup angelegt: $(basename "$bak")"
}

# KEY = <rhs> setzen/erzeugen (eine Zeile)
py_set_kv() {
  local key="$1" rhs="$2"
  python3 - "$CFG" "$key" "$rhs" <<'PY'
import re, sys
path, key, rhs = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path, 'r', encoding='utf-8') as f:
    txt = f.read()
pat = re.compile(rf'(?m)^\s*{re.escape(key)}\s*=\s*.*$')
rep = f"{key} = {rhs}"
if not pat.search(txt):
    ins_pat = re.compile(r'(?m)^\s*#\s*CRONTABS\b')
    m = ins_pat.search(txt)
    if m:
        pos = m.start()
        txt = txt[:pos] + rep + "\n" + txt[pos:]
    else:
        txt = txt.rstrip() + "\n" + rep + "\n"
else:
    txt = pat.sub(rep, txt, count=1)
with open(path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(txt)
PY
}

# Aktuellen Wert rechts von "KEY =" holen
get_val() {
  local key="$1"
  awk -v k="$key" '
    $0 ~ "^[[:space:]]*"k"[[:space:]]*=" {
      sub(/^[[:space:]]*[^=]+=[[:space:]]*/,"",$0);
      print $0; exit
    }' "$CFG"
}

# CRONTABS pflegen: upsert oder remove eines Items anhand "comment"
py_cron_edit() {
  local op="$1"
  shift
  python3 - "$CFG" "$op" "$@" <<'PY'
import re, sys

path = sys.argv[1]
op   = sys.argv[2]

def load_text(p):
    with open(p, 'r', encoding='utf-8') as f:
        return f.read()

def save_text(p, t):
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(t)

txt = load_text(path)

# Nicht-gieriger Match fuer CRONTABS = [ ... ]
m = re.search(r'(?ms)^\s*CRONTABS\s*=\s*\[(.*?)\]\s*', txt)
if not m:
    # Minimalen Block vor einer Marker-Zone oder am Ende einfuegen
    anchor = re.search(r'(?m)^\s*#{5,}.*$', txt)
    block = "CRONTABS = [\n]\n\n"
    if anchor:
        pos = anchor.start()
        txt = txt[:pos] + block + txt[pos:]
    else:
        txt = txt.rstrip() + "\n" + block
    m = re.search(r'(?ms)^\s*CRONTABS\s*=\s*\[(.*?)\]\s*', txt)

start, end = m.span()
inside = m.group(1)

def split_items(s):
    parts, buf, depth = [], "", 0
    i = 0
    while i < len(s):
        ch = s[i]
        buf += ch
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                parts.append(buf.strip())
                buf = ""
                j = i + 1
                while j < len(s) and s[j] in " \t\r\n,":
                    j += 1
                i = j - 1
        i += 1
    return [p for p in parts if p.startswith('{') and p.endswith('}')]

def parse_comment(item_text):
    m = re.search(r'"comment"\s*:\s*"([^"]+)"', item_text)
    return m.group(1) if m else None

items = split_items(inside)

def dict_to_text(d):
    keys = ["comment","schedule","command"]
    lines = []
    lines.append("    {")
    for idx,k in enumerate(keys):
        v = d.get(k, "")
        v = v.replace('\\', '\\\\').replace('"', '\\"')
        lines.append(f'        "comment": "{v}"' if k=="comment" else f'        "{k}": "{v}"')
        if idx < len(keys)-1:
            lines[-1] += ","
    lines.append("    }")
    return "\n".join(lines)

def build_inside(items_texts):
    if not items_texts:
        return "\n"
    return "\n" + ",\n".join(items_texts) + "\n"

if op == "upsert":
    comment = sys.argv[3]
    schedule = sys.argv[4]
    command  = sys.argv[5]
    payload = {"comment": comment, "schedule": schedule, "command": command}
    rendered = dict_to_text(payload)
    replaced = False
    new_items = []
    for it in items:
        c = parse_comment(it)
        if c == comment:
            new_items.append(rendered)
            replaced = True
        else:
            new_items.append(it)
    if not replaced:
        new_items.append(rendered)
    new_inside = build_inside(new_items)
    new_block = "CRONTABS = [" + new_inside + "]\n"
    txt = txt[:start] + new_block + txt[end:]
    save_text(path, txt)
    sys.exit(0)

elif op == "remove":
    comment = sys.argv[3]
    new_items = []
    for it in items:
        c = parse_comment(it)
        if c != comment:
            new_items.append(it)
    new_inside = build_inside(new_items)
    new_block = "CRONTABS = [" + new_inside + "]\n"
    txt = txt[:start] + new_block + txt[end:]
    save_text(path, txt)
    sys.exit(0)

else:
    sys.exit(2)
PY
}

# Standard-Kommandos fuer Cronjobs
CRON_CMD_RPSTAT='cd '"$ROOT_DIR"' && python3 -m scripts.raspi_status'
CRON_CMD_CFGUP='cd '"$ROOT_DIR"' && python3 -m scripts.upload_config_json'
CRON_CMD_BME='cd '"$ROOT_DIR"' && python3 -m scripts.bme280_logger'
CRON_CMD_TSL='cd '"$ROOT_DIR"' && python3 -m scripts.tsl2591_logger'
CRON_CMD_DS='cd '"$ROOT_DIR"' && python3 -m scripts.ds18b20_logger'
CRON_CMD_MLX='cd '"$ROOT_DIR"' && python3 -m scripts.mlx90614_logger'
CRON_CMD_KP='cd '"$ROOT_DIR"' && python3 -m scripts.kpindex_logger'
CRON_CMD_ANA='cd '"$ROOT_DIR"' && python3 -m scripts.analemma'
CRON_CMD_IMGUP='cd '"$ROOT_DIR"' && python3 -m scripts.run_image_upload'
CRON_CMD_NUP='cd '"$ROOT_DIR"' && python3 -m scripts.run_nightly_upload'
CRON_CMD_SQM='cd '"$ROOT_DIR"' && python3 -m scripts.sqm_camera_logger'
CRON_CMD_SQMP='cd '"$ROOT_DIR"' && python3 -m scripts.plot_sqm_night'

# Cron-Schedule zu einem Kommentar aus dem CRONTABS-Block lesen
cron_get_schedule() {
  local comment="$1"
  python3 - "$CFG" "$comment" <<'PY'
import re, sys
path, target = sys.argv[1], sys.argv[2]
txt = open(path, encoding="utf-8").read()

m = re.search(r'(?ms)^\s*CRONTABS\s*=\s*\[(.*?)\]\s*', txt)
if not m:
    sys.exit(0)
inside = m.group(1)

parts, buf, depth = [], "", 0
i = 0
while i < len(inside):
    ch = inside[i]
    buf += ch
    if ch == "{":
        depth += 1
    elif ch == "}":
        depth -= 1
        if depth == 0:
            parts.append(buf.strip())
            buf = ""
            j = i + 1
            while j < len(inside) and inside[j] in " \t\r\n,":
                j += 1
            i = j - 1
    i += 1

for p in parts:
    mc = re.search(r'"comment"\s*:\s*"([^"]+)"', p)
    if mc and mc.group(1) == target:
        ms = re.search(r'"schedule"\s*:\s*"([^"]+)"', p)
        if ms:
            print(ms.group(1))
        break
PY
}

# Aus */N * * * * das N herausziehen (Fallback 1)
interval_from_schedule() {
  local sched="$1"
  if [[ "$sched" =~ ^[[:space:]]*\*/([0-9]+)[[:space:]]+\*[[:space:]]+\*[[:space:]]+\*[[:space:]]+\*[[:space:]]*$ ]]; then
    echo "${BASHREMATCH[1]}"
  else
    echo "1"
  fi
}

# Cron-Schedule aus Minuten bauen
make_schedule_from_minutes() {
  local m="$1"
  if ! [[ "$m" =~ ^[0-9]+$ ]]; then m=1; fi
  if [ "$m" -lt 1 ]; then m=1; fi
  echo "*/$m * * * *"
}

# Intervall mit Default (aus vorhandenem Cron oder Fallback) lesen
read_interval_with_default() {
  local comment="$1" fallback="$2"
  local sched defN ans
  sched="$(cron_get_schedule "$comment" || true)"
  if [ -n "$sched" ]; then
    defN="$(interval_from_schedule "$sched")"
  else
    defN="$fallback"
  fi
  read -r -p "Abfrage-Intervall in Minuten [$defN]: " ans
  if ! [[ "$ans" =~ ^[0-9]+$ ]]; then ans="$defN"; fi
  if [ "$ans" -lt 1 ]; then ans=1; fi
  echo "$ans"
}

# Anzeigen
show_current() {
  echo "-------------------------------------------------"
  echo "Aktuelle Sensor-Einstellungen aus askutils/config.py"
  echo "-------------------------------------------------"
  printf "%-26s = %s\n" "BME280_ENABLED"        "$(get_val BME280_ENABLED)"
  printf "%-26s = %s\n" "BME280_I2C_ADDRESS"    "$(get_val BME280_I2C_ADDRESS)"
  printf "%-26s = %s\n" "BME280_OVERLAY"        "$(get_val BME280_OVERLAY)"
  echo
  printf "%-26s = %s\n" "TSL2591_ENABLED"       "$(get_val TSL2591_ENABLED)"
  printf "%-26s = %s\n" "TSL2591_I2C_ADDRESS"   "$(get_val TSL2591_I2C_ADDRESS)"
  printf "%-26s = %s\n" "TSL2591_SQM2_LIMIT"    "$(get_val TSL2591_SQM2_LIMIT)"
  printf "%-26s = %s\n" "TSL2591_SQM_CORRECTION" "$(get_val TSL2591_SQM_CORRECTION)"
  printf "%-26s = %s\n" "TSL2591_OVERLAY"       "$(get_val TSL2591_OVERLAY)"
  echo
  printf "%-26s = %s\n" "DS18B20_ENABLED"       "$(get_val DS18B20_ENABLED)"
  printf "%-26s = %s\n" "DS18B20_OVERLAY"       "$(get_val DS18B20_OVERLAY)"
  echo
  printf "%-26s = %s\n" "MLX90614_ENABLED"      "$(get_val MLX90614_ENABLED 2>/dev/null || echo False)"
  printf "%-26s = %s\n" "MLX90614_I2C_ADDRESS"  "$(get_val MLX90614_I2C_ADDRESS 2>/dev/null || echo 0x5A)"
  echo
  printf "%-26s = %s\n" "KPINDEX_OVERLAY"       "$(get_val KPINDEX_OVERLAY)"
  printf "%-26s = %s\n" "ANALEMMA_ENABLED"      "$(get_val ANALEMMA_ENABLED)"
  echo "-------------------------------------------------"
}

yesno_to_bool() {
  local ans="$1"
  if [[ "$ans" =~ ^[YyJj] ]]; then echo "True"; else echo "False"; fi
}

prompt_def() {
  local p="$1" d="$2" r
  read -r -p "$p [$d]: " r
  echo "${r:-$d}"
}

# Sensor-spezifische Editoren inkl. CRONTABS Upsert/Remove mit Intervall

edit_bme280() {
  echo "=== BME280 ==="
  local en_def addr_def ov_def
  en_def="$(get_val BME280_ENABLED)"; addr_def="$(get_val BME280_I2C_ADDRESS)"; ov_def="$(get_val BME280_OVERLAY)"
  read -r -p "BME280 aktivieren? (y/n) [$( [[ "$en_def" == "True" ]] && echo y || echo n )]: " yn
  local en
  en="$(yesno_to_bool "${yn:-$( [[ "$en_def" == "True" ]] && echo y || echo n )}")"
  local addr ov
  local interval sched
  if [ "$en" = "True" ]; then
    addr="$(prompt_def "I2C-Adresse (hex)" "$addr_def")"
    read -r -p "Overlay aktivieren? (y/n) [$( [[ "$ov_def" == "True" ]] && echo y || echo n )]: " ovyn
    ov="$(yesno_to_bool "${ovyn:-$( [[ "$ov_def" == "True" ]] && echo y || echo n )}")"
    interval="$(read_interval_with_default "BME280 Sensor" 1)"
    sched="$(make_schedule_from_minutes "$interval")"
  else
    addr="0x00"; ov="False"
  fi
  backup_cfg
  py_set_kv BME280_ENABLED "$en"
  py_set_kv BME280_I2C_ADDRESS "$addr"
  py_set_kv BME280_OVERLAY "$ov"

  if [ "$en" = "True" ]; then
    py_cron_edit upsert "BME280 Sensor" "$sched" "$CRON_CMD_BME"
  else
    py_cron_edit remove "BME280 Sensor"
  fi
  echo "BME280 aktualisiert."
}

edit_tsl2591() {
  echo "=== TSL2591 ==="
  local en_def addr_def lim_def corr_def ov_def
  en_def="$(get_val TSL2591_ENABLED)"
  addr_def="$(get_val TSL2591_I2C_ADDRESS)"
  lim_def="$(get_val TSL2591_SQM2_LIMIT)"
  corr_def="$(get_val TSL2591_SQM_CORRECTION)"
  ov_def="$(get_val TSL2591_OVERLAY)"
  read -r -p "TSL2591 aktivieren? (y/n) [$( [[ "$en_def" == "True" ]] && echo y || echo n )]: " yn
  local en
  en="$(yesno_to_bool "${yn:-$( [[ "$en_def" == "True" ]] && echo y || echo n )}")"
  local addr lim corr ov
  local interval sched
  if [ "$en" = "True" ]; then
    addr="$(prompt_def "I2C-Adresse (hex)" "$addr_def")"
    lim="$(prompt_def "SQM2-Limit (float)" "$lim_def")"
    corr="$(prompt_def "SQM-Korrektur (float)" "$corr_def")"
    read -r -p "Overlay aktivieren? (y/n) [$( [[ "$ov_def" == "True" ]] && echo y || echo n )]: " ovyn
    ov="$(yesno_to_bool "${ovyn:-$( [[ "$ov_def" == "True" ]] && echo y || echo n )}")"
    interval="$(read_interval_with_default "TSL2591 Sensor" 1)"
    sched="$(make_schedule_from_minutes "$interval")"
  else
    addr="0x00"; lim="0.0"; corr="0.0"; ov="False"
  fi
  backup_cfg
  py_set_kv TSL2591_ENABLED "$en"
  py_set_kv TSL2591_I2C_ADDRESS "$addr"
  py_set_kv TSL2591_SQM2_LIMIT "$lim"
  py_set_kv TSL2591_SQM_CORRECTION "$corr"
  py_set_kv TSL2591_OVERLAY "$ov"

  if [ "$en" = "True" ]; then
    py_cron_edit upsert "TSL2591 Sensor" "$sched" "$CRON_CMD_TSL"
  else
    py_cron_edit remove "TSL2591 Sensor"
  fi
  echo "TSL2591 aktualisiert."
}

edit_ds18b20() {
  echo "=== DS18B20 ==="
  local en_def ov_def
  en_def="$(get_val DS18B20_ENABLED)"; ov_def="$(get_val DS18B20_OVERLAY)"
  read -r -p "DS18B20 aktivieren? (y/n) [$( [[ "$en_def" == "True" ]] && echo y || echo n )]: " yn
  local en
  en="$(yesno_to_bool "${yn:-$( [[ "$en_def" == "True" ]] && echo y || echo n )}")"
  local ov="False"
  local interval sched
  if [ "$en" = "True" ]; then
    read -r -p "Overlay aktivieren? (y/n) [$( [[ "$ov_def" == "True" ]] && echo y || echo n )]: " ovyn
    ov="$(yesno_to_bool "${ovyn:-$( [[ "$ov_def" == "True" ]] && echo y || echo n )}")"
    interval="$(read_interval_with_default "DS18B20 Sensor" 1)"
    sched="$(make_schedule_from_minutes "$interval")"
  fi
  backup_cfg
  py_set_kv DS18B20_ENABLED "$en"
  py_set_kv DS18B20_OVERLAY "$ov"

  if [ "$en" = "True" ]; then
    py_cron_edit upsert "DS18B20 Sensor" "$sched" "$CRON_CMD_DS"
  else
    py_cron_edit remove "DS18B20 Sensor"
  fi
  echo "DS18B20 aktualisiert."
}

edit_mlx90614() {
  echo "=== MLX90614 ==="
  local en_def addr_def
  en_def="$(get_val MLX90614_ENABLED 2>/dev/null || echo False)"
  addr_def="$(get_val MLX90614_I2C_ADDRESS 2>/dev/null || echo 0x5A)"
  read -r -p "MLX90614 aktivieren? (y/n) [$( [[ "$en_def" == "True" ]] && echo y || echo n )]: " yn
  local en
  en="$(yesno_to_bool "${yn:-$( [[ "$en_def" == "True" ]] && echo y || echo n )}")"
  local addr
  local interval sched
  if [ "$en" = "True" ]; then
    addr="$(prompt_def "I2C-Adresse (hex)" "$addr_def")"
    interval="$(read_interval_with_default "MLX90614 Sensor" 1)"
    sched="$(make_schedule_from_minutes "$interval")"
  else
    addr="0x00"
  fi
  backup_cfg
  py_set_kv MLX90614_ENABLED "$en"
  py_set_kv MLX90614_I2C_ADDRESS "$addr"

  if [ "$en" = "True" ]; then
    py_cron_edit upsert "MLX90614 Sensor" "$sched" "$CRON_CMD_MLX"
  else
    py_cron_edit remove "MLX90614 Sensor"
  fi
  echo "MLX90614 aktualisiert."
}

toggle_kpindex() {
  echo "=== KP-Index Overlay ==="
  local def
  def="$(get_val KPINDEX_OVERLAY)"
  read -r -p "KP-Overlay aktivieren? (y/n) [$( [[ "$def" == "True" ]] && echo y || echo n )]: " yn
  local v
  v="$(yesno_to_bool "${yn:-$( [[ "$def" == "True" ]] && echo y || echo n )}")"
  backup_cfg
  py_set_kv KPINDEX_OVERLAY "$v"
  if [ "$v" = "True" ]; then
    py_cron_edit upsert "Generiere KPIndex Overlay variable" "*/15 * * * *" "$CRON_CMD_KP"
  else
    py_cron_edit remove "Generiere KPIndex Overlay variable"
  fi
  echo "KP-Index Overlay aktualisiert."
}

toggle_analemma() {
  echo "=== Analemma ==="
  local def
  def="$(get_val ANALEMMA_ENABLED)"
  read -r -p "Analemma aktivieren? (y/n) [$( [[ "$def" == "True" ]] && echo y || echo n )]: " yn
  local v
  v="$(yesno_to_bool "${yn:-$( [[ "$def" == "True" ]] && echo y || echo n )}")"
  backup_cfg
  py_set_kv ANALEMMA_ENABLED "$v"
  if [ "$v" = "True" ]; then
    py_cron_edit upsert "Generiere Analemma" "54/11 * * * *" "$CRON_CMD_ANA"
  else
    py_cron_edit remove "Generiere Analemma"
  fi
  echo "Analemma aktualisiert."
}

apply_crontabs_prompt() {
  echo
  read -r -p "Crontabs jetzt eintragen/aktualisieren? (y/n): " yn
  if [[ "$yn" =~ ^[YyJj] ]]; then
    ( cd "$ROOT_DIR" && python3 -m scripts.manage_crontabs )
  else
    echo "Hinweis: Crontabs lassen sich jederzeit anwenden mit:"
    echo "cd $ROOT_DIR && python3 -m scripts.manage_crontabs"
  fi
}

# Non-interaktiv: Key setzen oder Cron direkt pflegen
# Beispiele:
#   ./sensor_config.sh set TSL2591_SQM2_LIMIT 6.3
#   ./sensor_config.sh cron upsert "BME280 Sensor" "*/2 * * * *" "cd ... && python3 -m scripts.bme280_logger"
#   ./sensor_config.sh cron remove "BME280 Sensor"
if [[ "${1:-}" == "set" && $# -ge 3 ]]; then
  key="$2"; shift 2
  rhs="$*"
  echo "Setze ${key} = ${rhs}"
  #backup_cfg
  py_set_kv "$key" "$rhs"
  apply_crontabs_prompt
  exit 0
elif [[ "${1:-}" == "cron" && "${2:-}" == "upsert" && $# -ge 5 ]]; then
  shift 2
  comment="$1"; schedule="$2"; command="$3"
  backup_cfg
  py_cron_edit upsert "$comment" "$schedule" "$command"
  apply_crontabs_prompt
  exit 0
elif [[ "${1:-}" == "cron" && "${2:-}" == "remove" && $# -ge 3 ]]; then
  shift 2
  comment="$1"
  backup_cfg
  py_cron_edit remove "$comment"
  apply_crontabs_prompt
  exit 0
fi

# Interaktives Menue
while true; do
  echo
  echo "=========== Sensor Config ===========
1) Anzeigen (aktuelle Werte)
2) BME280 bearbeiten
3) TSL2591 bearbeiten
4) DS18B20 bearbeiten
5) MLX90614 bearbeiten
6) KP-Index Overlay (toggle)
7) Analemma (toggle)
8) Beenden
======================================"
  read -r -p "Auswahl: " sel
  case "${sel:-}" in
    1) show_current ;;
    2) edit_bme280; apply_crontabs_prompt ;;
    3) edit_tsl2591; apply_crontabs_prompt ;;
    4) edit_ds18b20; apply_crontabs_prompt ;;
    5) edit_mlx90614; apply_crontabs_prompt ;;
    6) toggle_kpindex; apply_crontabs_prompt ;;
    7) toggle_analemma; apply_crontabs_prompt ;;
    8) echo "Bye."; exit 0 ;;
    *) echo "Ungueltige Auswahl." ;;
  esac
done