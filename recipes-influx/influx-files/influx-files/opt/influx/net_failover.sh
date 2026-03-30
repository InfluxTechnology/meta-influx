#!/bin/sh

LOGFILE="/var/log/net_failover.log"
STATEFILE="/run/net_failover.active_if"
PING_TARGET="9.9.9.9"
DATE="$(date '+%Y-%m-%d %H:%M:%S')"

log() {
    echo "$DATE [INFO] $1" >> "$LOGFILE"
}

get_wlan_gateway() {
    ssid=$(iwgetid -r 2>/dev/null)
    gateway=""

    if [ -n "$ssid" ] && [ -f /opt/influx/wifi_gateways ]; then
        gateway=$(awk -v s="$ssid" '$1==s {print $2}' /opt/influx/wifi_gateways)
    fi

    if [ -z "$gateway" ]; then
        gateway=$(ip route | awk '/^default via/ && /wlan0/ {print $3; exit}')
    fi

    if [ -z "$gateway" ] || [ "$gateway" = "default" ]; then
        gateway=$(ip route | awk '/wlan0/ && /proto kernel/ {split($1,a,"."); print a[1]"."a[2]"."a[3]".1"; exit}')
    fi

    echo "$gateway"
}

wlan_is_healthy() {
    gateway="$1"
    [ -n "$gateway" ] || return 1
    ip route replace "$PING_TARGET" via "$gateway" dev wlan0 metric 5 2>/dev/null
    ping -I wlan0 -c 2 -W 2 "$PING_TARGET" >/dev/null 2>&1
    rc=$?
    ip route del "$PING_TARGET" dev wlan0 2>/dev/null
    return $rc
}

ppp_is_healthy() {
    ip link show ppp0 >/dev/null 2>&1 || return 1
    ip -4 addr show ppp0 | grep -q 'inet ' || return 1
    return 0
}

restart_rexgend_if_needed() {
    new_if="$1"
    [ -n "$new_if" ] || return 0

    old_if=""
    if [ -f "$STATEFILE" ]; then
        old_if=$(cat "$STATEFILE" 2>/dev/null)
    fi

    if [ "$old_if" != "$new_if" ]; then
        echo "$new_if" > "$STATEFILE"
        if [ "$new_if" = "none" ]; then
            log "Active uplink changed: ${old_if:-none} -> none. Waiting for a healthy uplink before restarting rexgend.service"
        else
            log "Active uplink changed: ${old_if:-none} -> $new_if. Restarting rexgend.service"
            if systemctl restart rexgend.service; then
                log "rexgend.service restarted successfully"
            else
                log "Failed to restart rexgend.service"
            fi
        fi
    fi
}

wlan_gateway=$(get_wlan_gateway)
active_if=""

if wlan_is_healthy "$wlan_gateway"; then
    active_if="wlan0"
    ip route del default dev ppp0 2>/dev/null
    if ! ip route | grep -q "^default via $wlan_gateway dev wlan0"; then
        ip route del default dev wlan0 2>/dev/null
        ip route replace default via "$wlan_gateway" dev wlan0 metric 10 2>/dev/null
    fi
    log "Switched to wlan0 as the default route"
elif ppp_is_healthy; then
    active_if="ppp0"
    ip route del default dev wlan0 2>/dev/null
    ip route replace default dev ppp0 metric 100 2>/dev/null
    log "wlan0 is down, switching to ppp0"
else
    active_if="none"
    log "No healthy uplink detected; keeping current routes"
fi

restart_rexgend_if_needed "$active_if"
