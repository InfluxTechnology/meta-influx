#!/bin/sh
# sys_loging.sh — CPU/MEM/TEMP min/avg, daily max, download speed, GNSS location

CONF_FILE="$(dirname "$0")/rex_sys_log.conf"
[ -f "$CONF_FILE" ] && . "$CONF_FILE" || {
    echo "Missing config file: $CONF_FILE" >&2
    exit 1
}

CPU_MAX_FILE="$LOG_DIR/cpu_max.state"
MEM_MAX_FILE="$LOG_DIR/mem_max.state"
TEMP_MAX_FILE="$LOG_DIR/temp_max.state"

SERIAL=$(cat /home/root/rexusb/var/serial)

mkdir -p "$LOG_DIR"
DAY=$(date +%F)
LOG_FILE="$LOG_DIR/sys_usage_${DAY}.log"
LAST_DAY="$DAY"

ts_now() { date "+%Y-%m-%d %H:%M:%S"; }
log_line() { echo "$1" >> "$LOG_FILE"; }

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
  START=$(date +%s)
  curl -s -o "$TMP" "$URL"
  END=$(date +%s)
  rm -f "$TMP"
  DUR=$((END-START))
  [ "$DUR" -gt 0 ] && echo $((1024 / DUR)) || echo 0
}

upload_pending_logs() {
    CLOUD_HANDLER="/home/root/rexusb/cloud/cloud_handler.sh"
    DAY=$(date +%F)
    CURRENT_LOG="sys_usage_${DAY}.log"
    if [ -x "$CLOUD_HANDLER" ]; then
        for PENDING in "$LOG_DIR"/*.log; do
            [ -f "$PENDING" ] || continue
            PENDING_NAME=$(basename "$PENDING")
            # Skip the current day's log file
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


# ---- Main loop ----
while true; do
  NOW=$(date +%s)
  TS=$(ts_now)
  DAY_NOW=$(date +%F)

    # ---- Daily rotation & reset MAX ----
  if [ "$DAY_NOW" != "$LAST_DAY" ]; then
      PREV_FILE="$LOG_DIR/sys_usage_${LAST_DAY}.log"
      CLOUD_FILE_NAME="sys_usage_${LAST_DAY}.log"

      # Write yesterday's MAX values
      echo "$LAST_TS $SERIAL: CPU_MAX=${CPU_MAX}%" >> "$PREV_FILE"
      echo "$LAST_TS $SERIAL: MEM_MAX=${MEM_MAX}%" >> "$PREV_FILE"
      echo "$LAST_TS $SERIAL: TEMP_MAX=${TEMP_MAX}C" >> "$PREV_FILE"

      # Reset MAX values
      CPU_MAX=0; MEM_MAX=0; TEMP_MAX=0
      echo 0 > "$CPU_MAX_FILE"
      echo 0 > "$MEM_MAX_FILE"
      echo 0 > "$TEMP_MAX_FILE"

      # Switch to new daily file (always, even if upload fails)
      LAST_DAY="$DAY_NOW"
      LOG_FILE="$LOG_DIR/sys_usage_${LAST_DAY}.log"

      # Upload all pending .log files
      upload_pending_logs

      # Cleanup: delete archived logs older than 7 days
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

  LAST_TS="$TS"

  # ---- Retry pending uploads hourly ----
  upload_pending_logs

  sleep 5
done
