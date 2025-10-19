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

# --- Keine Backups mehr schreiben (No-Op) ---
backup_cfg() { :; }

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

# Aktuellen Wert rechts von "KEY =" holen (Kommentare entfernen)
get_val() {
  local key="$1"
  awk -v k="$key" '
    $0 ~ "^[[:space:]]*"k"[[:space:]]*=" {
      line=$0
      sub(/^[[:space:]]*[^=]+=[[:space:]]*/,"",line)  # links bis "=" weg
      sub(/#.*/,"",line)                              # Inline-Kommentar weg
      gsub(/^[[:space:]]+|[[:space:]]+$/,"",line)     # trim
      print line
      exit
    }' "$CFG"
}

# ---------------------------------------------------------------------
# CRONTABS-Tools und Hilfsfunktionen
# ---------------------------------------------------------------------

py_cron_edit() {
  local op="$1"
  shift
  python3 - "$CFG" "$op" "$@" <<'PY'
import re, sys
path = sys.argv[1]; op = sys.argv[2]

def load_text(p): return open(p, encoding='utf-8').read()
def save_text(p,t): open(p,'w',encoding='utf-8',newline='\n').write(t)
txt = load_text(path)

m = re.search(r'(?ms)^\s*CRONTABS\s*=\s*\[(.*?)\]\s*', txt)
if not m:
    anchor = re.search(r'(?m)^\s*#{5,}.*$', txt)
    block = "CRONTABS = [\n]\n\n"
    if anchor:
        txt = txt[:anchor.start()] + block + txt[anchor.start():]
    else:
        txt = txt.rstrip() + "\n" + block
    m = re.search(r'(?ms)^\s*CRONTABS\s*=\s*\[(.*?)\]\s*', txt)
start,end = m.span(); inside=m.group(1)

def split_items(s):
    parts,buf,depth=[], "",0
    i=0
    while i<len(s):
        ch=s[i]; buf+=ch
        if ch=='{': depth+=1
        elif ch=='}':
            depth-=1
            if depth==0:
                parts.append(buf.strip()); buf=""
                j=i+1
                while j<len(s) and s[j] in " \t\r\n,": j+=1
                i=j-1
        i+=1
    return [p for p in parts if p.startswith('{') and p.endswith('}')]

def parse_comment(t):
    m=re.search(r'"comment"\s*:\s*"([^"]+)"',t)
    return m.group(1) if m else None

def dict_to_text(d):
    keys=["comment","schedule","command"]
    lines=["    {"]
    for i,k in enumerate(keys):
        v=d.get(k,"").replace('\\','\\\\').replace('"','\\"')
        lines.append(f'        "{k}": "{v}"' + ("," if i<len(keys)-1 else ""))
    lines.append("    }")
    return "\n".join(lines)

def build_inside(l): return "\n" + ",\n".join(l) + "\n" if l else "\n"

items=split_items(inside)
if op=="upsert":
    comment,schedule,command=sys.argv[3:6]
    payload={"comment":comment,"schedule":schedule,"command":command}
    new=dict_to_text(payload)
    replaced=False; new_items=[]
    for it in items:
        if parse_comment(it)==comment: new_items.append(new); replaced=True
        else: new_items.append(it)
    if not replaced: new_items.append(new)
    txt=txt[:start]+"CRONTABS = ["+build_inside(new_items)+"]\n"+txt[end:]
    save_text(path,txt)
elif op=="remove":
    comment=sys.argv[3]
    new_items=[it for it in items if parse_comment(it)!=comment]
    txt=txt[:start]+"CRONTABS = ["+build_inside(new_items)+"]\n"+txt[end:]
    save_text(path,txt)
PY
}

# Standard-Kommandos für Cronjobs
CRON_CMD_BME='cd '"$ROOT_DIR"' && python3 -m scripts.bme280_logger'
CRON_CMD_TSL='cd '"$ROOT_DIR"' && python3 -m scripts.tsl2591_logger'
CRON_CMD_DS='cd '"$ROOT_DIR"' && python3 -m scripts.ds18b20_logger'
CRON_CMD_DHT11='cd '"$ROOT_DIR"' && python3 -m scripts.dht11_logger'
CRON_CMD_DHT22='cd '"$ROOT_DIR"' && python3 -m scripts.dht22_logger'
CRON_CMD_MLX='cd '"$ROOT_DIR"' && python3 -m scripts.mlx90614_logger'
CRON_CMD_KP='cd '"$ROOT_DIR"' && python3 -m scripts.kpindex_logger'
CRON_CMD_ANA='cd '"$ROOT_DIR"' && python3 -m scripts.analemma'
CRON_CMD_IMGUP='cd '"$ROOT_DIR"' && python3 -m scripts.run_image_upload'
CRON_CMD_NUP='cd '"$ROOT_DIR"' && python3 -m scripts.run_nightly_upload'
CRON_CMD_SQM='cd '"$ROOT_DIR"' && python3 -m scripts.sqm_camera_logger'
CRON_CMD_SQMP='cd '"$ROOT_DIR"' && python3 -m scripts.plot_sqm_night'

# ---------------------------------------------------------------------
# Hilfsfunktionen für Cron-Schedules
# ---------------------------------------------------------------------

cron_get_schedule() {
  local comment="$1"
  python3 - "$CFG" "$comment" <<'PY'
import re,sys
txt=open(sys.argv[1],encoding="utf-8").read()
target=sys.argv[2]
m=re.search(r'(?ms)^\s*CRONTABS\s*=\s*\[(.*?)\]\s*',txt)
if not m: sys.exit(0)
inside=m.group(1)
for block in re.findall(r'\{.*?\}',inside,re.S):
    c=re.search(r'"comment"\s*:\s*"([^"]+)"',block)
    if c and c.group(1)==target:
        s=re.search(r'"schedule"\s*:\s*"([^"]+)"',block)
        if s: print(s.group(1)); break
PY
}

# robust gegen set -u und fehlende Matches
interval_from_schedule() {
  local sched="${1:-}"
  local N=""
  if [[ "${sched}" =~ ^[[:space:]]*\*/([0-9]+)[[:space:]]+\*[[:space:]]+\*[[:space:]]+\*[[:space:]]+\*[[:space:]]*$ ]]; then
    N="${BASH_REMATCH[1]}"
  fi
  if [[ -z "${N}" ]]; then echo "1"; else echo "${N}"; fi
}

make_schedule_from_minutes() {
  local m="${1:-1}"
  [[ "$m" =~ ^[0-9]+$ ]] || m=1
  (( m<1 )) && m=1
  echo "*/$m * * * *"
}

read_interval_with_default() {
  local comment="$1" fallback="$2"
  local sched defN ans
  sched="$(cron_get_schedule "$comment" || true)"
  defN="$(interval_from_schedule "${sched:-}")"
  [[ -z "$defN" ]] && defN="$fallback"
  read -r -p "Abfrage-Intervall in Minuten [$defN]: " ans
  [[ "$ans" =~ ^[0-9]+$ ]] || ans="$defN"
  (( ans<1 )) && ans=1
  echo "$ans"
}

# ---------------------------------------------------------------------
# Anzeige
# ---------------------------------------------------------------------

show_current() {
  echo "-------------------------------------------------"
  echo "Aktuelle Sensor-Einstellungen aus askutils/config.py"
  echo "-------------------------------------------------"
  printf "%-25s = %s\n" "BME280_ENABLED"  "$(get_val BME280_ENABLED)"
  printf "%-25s = %s\n" "TSL2591_ENABLED" "$(get_val TSL2591_ENABLED)"
  printf "%-25s = %s\n" "DS18B20_ENABLED" "$(get_val DS18B20_ENABLED)"
  printf "%-25s = %s\n" "DHT11_ENABLED"   "$(get_val DHT11_ENABLED 2>/dev/null)"
  printf "%-25s = %s\n" "DHT22_ENABLED"   "$(get_val DHT22_ENABLED 2>/dev/null)"
  printf "%-25s = %s\n" "MLX90614_ENABLED" "$(get_val MLX90614_ENABLED 2>/dev/null)"
  echo "-------------------------------------------------"
}

# ---------------------------------------------------------------------
# Eingabe-Helfer
# ---------------------------------------------------------------------

yesno_to_bool() { [[ "$1" =~ ^[YyJj] ]] && echo "True" || echo "False"; }
prompt_def() { local p="$1" d="$2" r; read -r -p "$p [$d]: " r; echo "${r:-$d}"; }

# ---------------------------------------------------------------------
# Sensor-Editoren
# ---------------------------------------------------------------------

edit_bme280() {
  echo "=== BME280 ==="
  local en_def addr_def ov_def
  en_def="$(get_val BME280_ENABLED)"; addr_def="$(get_val BME280_I2C_ADDRESS)"; ov_def="$(get_val BME280_OVERLAY)"
  read -r -p "BME280 aktivieren? (y/n) [$( [[ "$en_def" == "True" ]] && echo y || echo n )]: " yn
  local en=$(yesno_to_bool "${yn:-$( [[ "$en_def" == "True" ]] && echo y || echo n )}")
  local addr ov interval sched
  if [ "$en" = "True" ]; then
    addr="$(prompt_def "I2C-Adresse (hex)" "$addr_def")"
    read -r -p "Overlay aktivieren? (y/n) [$( [[ "$ov_def" == "True" ]] && echo y || echo n )]: " ovyn
    ov="$(yesno_to_bool "${ovyn:-$( [[ "$ov_def" == "True" ]] && echo y || echo n )}")"
    interval="$(read_interval_with_default "BME280 Sensor" 1)"
    sched="$(make_schedule_from_minutes "$interval")"
  else
    addr="0x00"; ov="False"
  fi
  py_set_kv BME280_ENABLED "$en"
  py_set_kv BME280_I2C_ADDRESS "$addr"
  py_set_kv BME280_OVERLAY "$ov"
  if [ "$en" = "True" ]; then py_cron_edit upsert "BME280 Sensor" "$sched" "$CRON_CMD_BME"; else py_cron_edit remove "BME280 Sensor"; fi
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
  local en=$(yesno_to_bool "${yn:-$( [[ "$en_def" == "True" ]] && echo y || echo n )}")
  local addr lim corr ov interval sched
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
  py_set_kv TSL2591_ENABLED "$en"
  py_set_kv TSL2591_I2C_ADDRESS "$addr"
  py_set_kv TSL2591_SQM2_LIMIT "$lim"
  py_set_kv TSL2591_SQM_CORRECTION "$corr"
  py_set_kv TSL2591_OVERLAY "$ov"
  if [ "$en" = "True" ]; then py_cron_edit upsert "TSL2591 Sensor" "$sched" "$CRON_CMD_TSL"; else py_cron_edit remove "TSL2591 Sensor"; fi
  echo "TSL2591 aktualisiert."
}

edit_ds18b20() {
  echo "=== DS18B20 ==="
  local en_def ov_def
  en_def="$(get_val DS18B20_ENABLED)"; ov_def="$(get_val DS18B20_OVERLAY)"
  read -r -p "DS18B20 aktivieren? (y/n) [$( [[ "$en_def" == "True" ]] && echo y || echo n )]: " yn
  local en=$(yesno_to_bool "${yn:-$( [[ "$en_def" == "True" ]] && echo y || echo n )}")
  local ov="False" interval sched
  if [ "$en" = "True" ]; then
    read -r -p "Overlay aktivieren? (y/n) [$( [[ "$ov_def" == "True" ]] && echo y || echo n )]: " ovyn
    ov="$(yesno_to_bool "${ovyn:-$( [[ "$ov_def" == "True" ]] && echo y || echo n )}")"
    interval="$(read_interval_with_default "DS18B20 Sensor" 1)"
    sched="$(make_schedule_from_minutes "$interval")"
  fi
  py_set_kv DS18B20_ENABLED "$en"
  py_set_kv DS18B20_OVERLAY "$ov"
  if [ "$en" = "True" ]; then py_cron_edit upsert "DS18B20 Sensor" "$sched" "$CRON_CMD_DS"; else py_cron_edit remove "DS18B20 Sensor"; fi
  echo "DS18B20 aktualisiert."
}

# --- NEU: DHT11 ---
edit_dht11() {
  echo "=== DHT11 ==="
  local en_def gpio_def ret_def del_def ov_def
  en_def="$(get_val DHT11_ENABLED 2>/dev/null || echo False)"
  gpio_def="$(get_val DHT11_GPIO_BCM 2>/dev/null || echo 6)"
  ret_def="$(get_val DHT11_RETRIES 2>/dev/null || echo 10)"
  del_def="$(get_val DHT11_RETRY_DELAY 2>/dev/null || echo 0.3)"
  ov_def="$(get_val DHT11_OVERLAY 2>/dev/null || echo True)"
  read -r -p "DHT11 aktivieren? (y/n) [$( [[ "$en_def" == "True" ]] && echo y || echo n )]: " yn
  local en=$(yesno_to_bool "${yn:-$( [[ "$en_def" == "True" ]] && echo y || echo n )}")
  local gpio ret del ov interval sched
  if [ "$en" = "True" ]; then
    gpio="$(prompt_def 'GPIO (BCM-Nummer)' "$gpio_def")"
    ret="$(prompt_def 'Retries pro Messung (Median)' "$ret_def")"
    del="$(prompt_def 'Retry-Delay in Sekunden' "$del_def")"
    read -r -p "Overlay aktivieren? (y/n) [$( [[ "$ov_def" == "True" ]] && echo y || echo n )]: " ovyn
    ov="$(yesno_to_bool "${ovyn:-$( [[ "$ov_def" == "True" ]] && echo y || echo n )}")"
    interval="$(read_interval_with_default 'DHT11 Sensor' 1)"
    sched="$(make_schedule_from_minutes "$interval")"
  else
    gpio="6"; ret="10"; del="0.3"; ov="False"
  fi
  py_set_kv DHT11_ENABLED "$en"
  py_set_kv DHT11_GPIO_BCM "$gpio"
  py_set_kv DHT11_RETRIES "$ret"
  py_set_kv DHT11_RETRY_DELAY "$del"
  py_set_kv DHT11_OVERLAY "$ov"
  if [ "$en" = "True" ]; then py_cron_edit upsert "DHT11 Sensor" "$sched" "$CRON_CMD_DHT11"; else py_cron_edit remove "DHT11 Sensor"; fi
  echo "DHT11 aktualisiert."
}

# --- NEU: DHT22 ---
edit_dht22() {
  echo "=== DHT22 ==="
  local en_def gpio_def ret_def del_def ov_def
  en_def="$(get_val DHT22_ENABLED 2>/dev/null || echo False)"
  gpio_def="$(get_val DHT22_GPIO_BCM 2>/dev/null || echo 6)"
  ret_def="$(get_val DHT22_RETRIES 2>/dev/null || echo 10)"
  del_def="$(get_val DHT22_RETRY_DELAY 2>/dev/null || echo 0.3)"
  ov_def="$(get_val DHT22_OVERLAY 2>/dev/null || echo True)"
  read -r -p "DHT22 aktivieren? (y/n) [$( [[ "$en_def" == "True" ]] && echo y || echo n )]: " yn
  local en=$(yesno_to_bool "${yn:-$( [[ "$en_def" == "True" ]] && echo y || echo n )}")
  local gpio ret del ov interval sched
  if [ "$en" = "True" ]; then
    gpio="$(prompt_def 'GPIO (BCM-Nummer)' "$gpio_def")"
    ret="$(prompt_def 'Retries pro Messung (Median)' "$ret_def")"
    del="$(prompt_def 'Retry-Delay in Sekunden' "$del_def")"
    read -r -p "Overlay aktivieren? (y/n) [$( [[ "$ov_def" == "True" ]] && echo y || echo n )]: " ovyn
    ov="$(yesno_to_bool "${ovyn:-$( [[ "$ov_def" == "True" ]] && echo y || echo n )}")"
    interval="$(read_interval_with_default 'DHT22 Sensor' 1)"
    sched="$(make_schedule_from_minutes "$interval")"
  else
    gpio="6"; ret="10"; del="0.3"; ov="False"
  fi
  py_set_kv DHT22_ENABLED "$en"
  py_set_kv DHT22_GPIO_BCM "$gpio"
  py_set_kv DHT22_RETRIES "$ret"
  py_set_kv DHT22_RETRY_DELAY "$del"
  py_set_kv DHT22_OVERLAY "$ov"
  if [ "$en" = "True" ]; then py_cron_edit upsert "DHT22 Sensor" "$sched" "$CRON_CMD_DHT22"; else py_cron_edit remove "DHT22 Sensor"; fi
  echo "DHT22 aktualisiert."
}

edit_mlx90614() {
  echo "=== MLX90614 ==="
  local en_def addr_def
  en_def="$(get_val MLX90614_ENABLED 2>/dev/null || echo False)"
  addr_def="$(get_val MLX90614_I2C_ADDRESS 2>/dev/null || echo 0x5A)"
  read -r -p "MLX90614 aktivieren? (y/n) [$( [[ "$en_def" == "True" ]] && echo y || echo n )]: " yn
  local en=$(yesno_to_bool "${yn:-$( [[ "$en_def" == "True" ]] && echo y || echo n )}")
  local addr interval sched
  if [ "$en" = "True" ]; then
    addr="$(prompt_def "I2C-Adresse (hex)" "$addr_def")"
    interval="$(read_interval_with_default "MLX90614 Sensor" 1)"
    sched="$(make_schedule_from_minutes "$interval")"
  else
    addr="0x00"
  fi
  py_set_kv MLX90614_ENABLED "$en"
  py_set_kv MLX90614_I2C_ADDRESS "$addr"
  if [ "$en" = "True" ]; then py_cron_edit upsert "MLX90614 Sensor" "$sched" "$CRON_CMD_MLX"; else py_cron_edit remove "MLX90614 Sensor"; fi
  echo "MLX90614 aktualisiert."
}

toggle_kpindex() {
  echo "=== KP-Index Overlay ==="
  local def
  def="$(get_val KPINDEX_OVERLAY)"
  read -r -p "KP-Overlay aktivieren? (y/n) [$( [[ "$def" == "True" ]] && echo y || echo n )]: " yn
  local v=$(yesno_to_bool "${yn:-$( [[ "$def" == "True" ]] && echo y || echo n )}")
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
  local v=$(yesno_to_bool "${yn:-$( [[ "$def" == "True" ]] && echo y || echo n )}")
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

# ---------------------------------------------------------------------
# Menü
# ---------------------------------------------------------------------

while true; do
  echo
  echo "=========== Sensor Config ===========
1) Anzeigen (aktuelle Werte)
2) BME280 bearbeiten
3) TSL2591 bearbeiten
4) DS18B20 bearbeiten
5) DHT11 bearbeiten
6) DHT22 bearbeiten
7) MLX90614 bearbeiten
8) KP-Index Overlay (toggle)
9) Analemma (toggle)
x) Beenden
======================================"
  read -r -p "Auswahl: " sel
  case "${sel:-}" in
    1) show_current ;;
    2) edit_bme280; apply_crontabs_prompt ;;
    3) edit_tsl2591; apply_crontabs_prompt ;;
    4) edit_ds18b20; apply_crontabs_prompt ;;
    5) edit_dht11; apply_crontabs_prompt ;;
    6) edit_dht22; apply_crontabs_prompt ;;
    7) edit_mlx90614; apply_crontabs_prompt ;;
    8) toggle_kpindex; apply_crontabs_prompt ;;
    9) toggle_analemma; apply_crontabs_prompt ;;
    x|X) echo "Bye."; exit 0 ;;
    *) echo "Ungueltige Auswahl." ;;
  esac
done
