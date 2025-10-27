#!/bin/sh

LOGFILE="/var/log/net_failover.log"
DATE="$(date '+%Y-%m-%d %H:%M:%S')"

# Ping using wlan0
ping -I wlan0 -c 2 -W 2 8.8.8.8 > /dev/null
WLAN_OK=$?

# Check if wlan0 is down
if [ "$WLAN_OK" -ne 0 ]; then
    echo "$DATE [INFO] wlan0 is down, switching to ppp0" >> "$LOGFILE"
    
    # If ppp0 doesn't already have a default route, add it
    ip route del default dev wlan0 2>/dev/null
    ip route add default dev ppp0 metric 100 2>/dev/null
    echo "$DATE [INFO] Added default route for ppp0" >> "$LOGFILE"
else
    # If wlan0 is up, ensure it's the default route
    ip route del default dev ppp0 2>/dev/null
    ip route add default dev wlan0 metric 20 2>/dev/null
    echo "$DATE [INFO] Switched to wlan0 as the default route" >> "$LOGFILE"
fi

