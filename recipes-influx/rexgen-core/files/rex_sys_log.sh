#!/bin/sh
# rex_sys_log.sh — CPU/MEM/TEMP min/avg, daily max, download speed, GNSS location.
#
# System-log sink owner:
#   All system-log writers (this script, rexgend CAN errors, cloud_sync NET_UPL)
#   append to a single symlink:  $LOG_DIR/system.log
#     - master switch [System] system_log = 1 -> symlink -> sys_usage_YYYY-MM-DD.log
#     - master switch [System] system_log = 0 -> symlink -> /dev/null   (writes discarded)
#   This script is the ONLY process that flips the symlink and rotates it daily.
#   When the switch is off it also skips its own (expensive) sampling entirely.

CONF_FILE="$(dirname "$0")/rex_sys_log.conf"
[ -f "$CONF_FILE" ] && . "$CONF_FILE" || {
    echo "Missing config file: $CONF_FILE" >&2
    exit 1
}

REXGEND_CONF="/data/rexgen/config/rexgend.conf"
SINK="$LOG_DIR/system.log"

CPU_MAX_FILE="$LOG_DIR/cpu_max.state"
MEM_MAX_FILE="$LOG_DIR/mem_max.state"
TEMP_MAX_FILE="$LOG_DIR/temp_max.state"

SERIAL=$(cat /home/root/rexusb/var/serial)

mkdir -p "$LOG_DIR"
DAY=$(date +%F)
LAST_DAY="$DAY"

ts_now() { date "+%Y-%m-%d %H:%M:%S"; }
log_line() { echo "$1" >> "$SINK"; }   # follows the symlink -> daily file or /dev/null

# ---- Master switch: read [System] system_log from rexgend.conf ----
# Section-aware, defaults to 0 (off) when the key/file is missing.
read_system_log() {
    awk '
        /^[[:space:]]*\[/ { sec=$0; gsub(/[[:space:]]/,"",sec); next }
        sec=="[System]" {
            line=$0; sub(/[#;].*/,"",line); gsub(/[[:space:]]/,"",line)
            n=index(line,"="); if(n==0) next
            if (substr(line,1,n-1)=="system_log") { print substr(line,n+1); exit }
        }
    ' "$REXGEND_CONF" 2>/dev/null
}

# ---- Point the sink symlink (only re-links when the target changes) ----
point_sink() {
    want="$1"                                  # "sys_usage_${DAY}.log" (relative) or "/dev/null"
    have=$(readlink "$SINK" 2>/dev/null)
    if [ "$have" != "$want" ]; then
        ln -sf "$want" "$SINK"
    fi
    # Make sure the daily target exists so appenders (e.g. rexgend, no O_CREAT) succeed.
    case "$want" in /dev/null) : ;; *) [ -e "$LOG_DIR/$want" ] || : > "$LOG_DIR/$want" ;; esac
}

# ---- Sensors ----
get_cpu_pct() {
  set -- $(sed -n 's/^cpu[ ]\+//p' /proc/stat | head -n1)
  u1=$1; n1=$2; s1=$3; i1=$4; w1=$5; ir1=$6; si1=$7; st1=$8
  total1=$((u1+n1+s1+i1+w1+ir1+si1+st1)); idle1=$((i1+w1))
  sleep 1
  set -- $(sed -n 's/^cpu[ ]\+//p' /proc/stat | head -n1)
  u2=$1; n2=$2; s2=$3; i2=$4; w2=$5; ir2=$6; si2=$7; st2=$8
  total2=$((u2+n2+s2+i2+w2+ir2+si2+st2)); idle2=$((i2+w2))
  awk -v t1="$total1" -v i1="$idle1" -v t2="$total2" -v i2="$idle2" \
      'BEGIN{dt=t2-t1; di=i2-i1; if(dt<=0){print 0}else{printf "%.0f",(1-(di/dt))*100}}'
}

get_ram_pct() {
  awk '
    /MemTotal:/ {mt=$2}
    /MemAvailable:/ {ma=$2}
    END{if(mt>0){printf "%.0f",((mt-ma)/mt)*100}else{print 0}}' /proc/meminfo
}

get_temp_c() {
  for f in /sys/class/thermal/thermal_zone*/temp /sys/class/hwmon/hwmon*/temp*_input; do
    [ -r "$f" ] || continue
    v=$(cat "$f" 2>/dev/null)
    case "$v" in ''|*[!0-9]*) continue ;; esac
    awk -v x="$v" 'BEGIN{printf "%.0f",(x>=1000)?x/1000:x}'
    return
  done
  echo 0
}

get_net_dl_kbps() {
  URL="http://speedtest.tele2.net/1MB.zip"
  TMP="/tmp/speedtest.$$"
  START=$(date +%s%3N)  # milliseconds
  curl -s -o "$TMP" "$URL"
  END=$(date +%s%3N)    # milliseconds
  rm -f "$TMP"
  DUR=$((END-START))
  [ "$DUR" -gt 0 ] && echo $((1024000 / DUR)) || echo 0
}

upload_pending_logs() {
    CLOUD_HANDLER="/home/root/rexusb/cloud/cloud_handler.sh"
    DAY=$(date +%F)
    CURRENT_LOG="sys_usage_${DAY}.log"
    if [ -x "$CLOUD_HANDLER" ]; then
        for PENDING in "$LOG_DIR"/sys_usage_*.log; do
            [ -f "$PENDING" ] || continue
            PENDING_NAME=$(basename "$PENDING")
            # Skip the current day's log file (it is the live sink target)
            if [ "$PENDING_NAME" = "$CURRENT_LOG" ]; then
                continue
            fi
            "$CLOUD_HANDLER" upload "$PENDING" "$PENDING_NAME"
            if [ $? -eq 0 ]; then
                echo "$TS $SERIAL: INFO upload succeeded for $PENDING_NAME, archiving" >> "$PENDING"
                gzip -f "$PENDING"
            else
                echo "$TS $SERIAL: WARN upload failed for $PENDING_NAME, will retry later" >> "$PENDING"
            fi
        done
    fi
}

# ---- GNSS Location ----
get_gnss_location() {
    [ -r "$GNSS_DEV" ] || { echo "0,0"; return; }
    LINE=$(timeout 2 grep -m1 "\$GPGGA" "$GNSS_DEV" 2>/dev/null)
    if [ -n "$LINE" ]; then
        LAT=$(echo "$LINE" | awk -F',' '{print $3}')
        LAT_DIR=$(echo "$LINE" | awk -F',' '{print $4}')
        LON=$(echo "$LINE" | awk -F',' '{print $5}')
        LON_DIR=$(echo "$LINE" | awk -F',' '{print $6}')
        ALT=$(echo "$LINE" | awk -F',' '{print $10}')

        if [ -n "$LAT" ] && [ -n "$LON" ]; then
            LAT_DEC=$(echo "$LAT $LAT_DIR" | awk '{deg=int($1/100);min=$1-deg*100;dec=deg+(min/60);if($2=="S")dec=-dec;printf "%.6f",dec}')
            LON_DEC=$(echo "$LON $LON_DIR" | awk '{deg=int($1/100);min=$1-deg*100;dec=deg+(min/60);if($2=="W")dec=-dec;printf "%.6f",dec}')
            echo "${LAT_DEC},${LON_DEC},ALT=${ALT}m"
            return
        fi
    fi
    echo "0,0"
}


# ---- State ----
NOW=$(date +%s)
LAST_TS=$(ts_now)
LAST_MAX=$NOW

# CPU
CPU_MIN=100 CPU_SUM=0 CPU_COUNT=0
LAST_CPU_MIN=$NOW LAST_CPU_AVG=$NOW
[ -f "$CPU_MAX_FILE" ] && CPU_MAX=$(cat "$CPU_MAX_FILE") || CPU_MAX=0

# MEM
MEM_MIN=100 MEM_SUM=0 MEM_COUNT=0
LAST_MEM_MIN=$NOW LAST_MEM_AVG=$NOW
[ -f "$MEM_MAX_FILE" ] && MEM_MAX=$(cat "$MEM_MAX_FILE") || MEM_MAX=0

# TEMP
TEMP_MIN=1000 TEMP_SUM=0 TEMP_COUNT=0
LAST_TEMP_MIN=$NOW LAST_TEMP_AVG=$NOW
[ -f "$TEMP_MAX_FILE" ] && TEMP_MAX=$(cat "$TEMP_MAX_FILE") || TEMP_MAX=0

# NET
LAST_SPEED=$NOW

# GNSS
LAST_GNSS=$NOW

# Pending upload retry
UPLOAD_RETRY_INTERVAL=3600   # 1 hour
LAST_UPLOAD_RETRY=$NOW

WAS_ON=-1   # force a sink update on first iteration


# ---- Main loop ----
while true; do
  NOW=$(date +%s)
  TS=$(ts_now)
  DAY_NOW=$(date +%F)

  # ---- Master switch ----
  ENABLED=$(read_system_log)
  [ "$ENABLED" = "1" ] || ENABLED=0

  if [ "$ENABLED" != "1" ]; then
      # Logging disabled: point sink at /dev/null (writes are discarded cheaply),
      # skip ALL sampling so we don't burn CPU, and idle.
      point_sink /dev/null
      WAS_ON=0
      sleep 5
      continue
  fi

  # Logging enabled: make sure the sink points at today's file.
  point_sink "sys_usage_${DAY_NOW}.log"
  # First time (or just turned on): reset the per-window accumulators.
  if [ "$WAS_ON" != "1" ]; then
      LAST_TS=$TS; LAST_MAX=$NOW
      LAST_CPU_MIN=$NOW; LAST_CPU_AVG=$NOW; LAST_MEM_MIN=$NOW; LAST_MEM_AVG=$NOW
      LAST_TEMP_MIN=$NOW; LAST_TEMP_AVG=$NOW; LAST_SPEED=$NOW; LAST_GNSS=$NOW
      WAS_ON=1
  fi

  # ---- Daily rotation & reset MAX ----
  if [ "$DAY_NOW" != "$LAST_DAY" ]; then
      PREV_FILE="$LOG_DIR/sys_usage_${LAST_DAY}.log"

      # Write yesterday's MAX values directly into the previous day's file
      echo "$LAST_TS $SERIAL: CPU_MAX=${CPU_MAX}%"  >> "$PREV_FILE"
      echo "$LAST_TS $SERIAL: MEM_MAX=${MEM_MAX}%"  >> "$PREV_FILE"
      echo "$LAST_TS $SERIAL: TEMP_MAX=${TEMP_MAX}C" >> "$PREV_FILE"

      # Reset MAX values
      CPU_MAX=0; MEM_MAX=0; TEMP_MAX=0
      echo 0 > "$CPU_MAX_FILE"; echo 0 > "$MEM_MAX_FILE"; echo 0 > "$TEMP_MAX_FILE"

      # Switch the sink to the new day's file
      LAST_DAY="$DAY_NOW"
      point_sink "sys_usage_${LAST_DAY}.log"

      # Upload all pending (non-current) .log files, then clean archives > 7 days
      upload_pending_logs
      find "$LOG_DIR" -name "sys_usage_*.log.gz" -type f -mtime +7 -exec rm -f {} \;
  fi


  # ---- Sample ----
  CPU=$(get_cpu_pct)
  MEM=$(get_ram_pct)
  TEMP=$(get_temp_c)

  # ---- CPU ----
  [ "$CPU" -lt "$CPU_MIN" ] && CPU_MIN=$CPU
  [ "$CPU" -gt "$CPU_MAX" ] && CPU_MAX=$CPU && echo "$CPU_MAX" > "$CPU_MAX_FILE"
  CPU_SUM=$((CPU_SUM + CPU)); CPU_COUNT=$((CPU_COUNT + 1))

  if [ $((NOW - LAST_CPU_MIN)) -ge $MIN_INTERVAL ]; then
    log_line "$TS $SERIAL: CPU_MIN=${CPU_MIN}%"
    CPU_MIN=100; LAST_CPU_MIN=$NOW
  fi
  if [ $((NOW - LAST_CPU_AVG)) -ge $AVG_INTERVAL ]; then
    CPU_AVG=$((CPU_SUM / CPU_COUNT))
    log_line "$TS $SERIAL: CPU_AVG=${CPU_AVG}%"
    CPU_SUM=0; CPU_COUNT=0; LAST_CPU_AVG=$NOW
  fi

  # ---- MEM ----
  [ "$MEM" -lt "$MEM_MIN" ] && MEM_MIN=$MEM
  [ "$MEM" -gt "$MEM_MAX" ] && MEM_MAX=$MEM && echo "$MEM_MAX" > "$MEM_MAX_FILE"
  MEM_SUM=$((MEM_SUM + MEM)); MEM_COUNT=$((MEM_COUNT + 1))

  if [ $((NOW - LAST_MEM_MIN)) -ge $MIN_INTERVAL ]; then
    log_line "$TS $SERIAL: MEM_MIN=${MEM_MIN}%"
    MEM_MIN=100; LAST_MEM_MIN=$NOW
  fi
  if [ $((NOW - LAST_MEM_AVG)) -ge $AVG_INTERVAL ]; then
    MEM_AVG=$((MEM_SUM / MEM_COUNT))
    log_line "$TS $SERIAL: MEM_AVG=${MEM_AVG}%"
    MEM_SUM=0; MEM_COUNT=0; LAST_MEM_AVG=$NOW
  fi

  # ---- TEMP ----
  [ "$TEMP" -lt "$TEMP_MIN" ] && TEMP_MIN=$TEMP
  [ "$TEMP" -gt "$TEMP_MAX" ] && TEMP_MAX=$TEMP && echo "$TEMP_MAX" > "$TEMP_MAX_FILE"
  TEMP_SUM=$((TEMP_SUM + TEMP)); TEMP_COUNT=$((TEMP_COUNT + 1))

  if [ $((NOW - LAST_TEMP_MIN)) -ge $MIN_INTERVAL ]; then
    log_line "$TS $SERIAL: TEMP_MIN=${TEMP_MIN}C"
    TEMP_MIN=1000; LAST_TEMP_MIN=$NOW
  fi
  if [ $((NOW - LAST_TEMP_AVG)) -ge $AVG_INTERVAL ]; then
    TEMP_AVG=$((TEMP_SUM / TEMP_COUNT))
    log_line "$TS $SERIAL: TEMP_AVG=${TEMP_AVG}C"
    TEMP_SUM=0; TEMP_COUNT=0; LAST_TEMP_AVG=$NOW
  fi

  # ---- NET ----
  if [ $((NOW - LAST_SPEED)) -ge $SPEED_INTERVAL ]; then
    DL=$(get_net_dl_kbps)
    log_line "$TS $SERIAL: NET_DL=${DL}KBps"
    LAST_SPEED=$NOW
  fi

  # ---- GNSS ----
  if [ $((NOW - LAST_GNSS)) -ge $GNSS_INTERVAL ]; then
    GNSS=$(get_gnss_location)
    log_line "$TS $SERIAL: GNSS=${GNSS}"
    LAST_GNSS=$NOW
  fi

  # ---- MAX VALUES ----
  if [ $((NOW - LAST_MAX)) -ge $MAX_INTERVAL ]; then
    log_line "$TS $SERIAL: CPU_MAX=${CPU_MAX}%"
    log_line "$TS $SERIAL: MEM_MAX=${MEM_MAX}%"
    log_line "$TS $SERIAL: TEMP_MAX=${TEMP_MAX}C"

    CPU_MAX=0; MEM_MAX=0; TEMP_MAX=0
    echo 0 > "$CPU_MAX_FILE"; echo 0 > "$MEM_MAX_FILE"; echo 0 > "$TEMP_MAX_FILE"
    LAST_MAX=$NOW
  fi

  LAST_TS="$TS"

  # ---- Retry pending uploads hourly ----
  if [ $((NOW - LAST_UPLOAD_RETRY)) -ge $UPLOAD_RETRY_INTERVAL ]; then
    upload_pending_logs
    LAST_UPLOAD_RETRY=$NOW
  fi

  sleep 5
done
