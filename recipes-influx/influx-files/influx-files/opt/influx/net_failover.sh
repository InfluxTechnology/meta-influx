#!/bin/sh

LOGFILE="/var/log/net_failover.log"
DATE="$(date '+%Y-%m-%d %H:%M:%S')"

ssid=$(iwgetid -r)  # get current SSID
if [ -f /opt/influx/wifi_gateways ]; then
    gateway=$(awk -v s="$ssid" '$1==s {print $2}' /opt/influx/wifi_gateways)
fi

# If gateway is empty, fall back to ip route
if [ -z "$gateway" ]; then
    gateway=$(ip route | awk '/^default via/ && /wlan0/ {print $3; exit}')
fi
if [ -z "$gateway" ] || [ "$gateway" = "default" ]; then
    gateway=$(ip route | awk '/wlan0/ && /proto kernel/ {split($1,a,"."); print a[1]"."a[2]"."a[3]".1"; exit}')
fi

# Add a host route to test target via wlan0 gateway, *without touching default
ip route replace 8.8.8.8 via "$gateway" dev wlan0 metric 5

# Ping using wlan0
ping -I wlan0 -c 2 -W 2 8.8.8.8 > /dev/null
WLAN_OK=$?

# Clean up the test route
ip route del 8.8.8.8 dev wlan0 2>/dev/null

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
  echo "$DATE [INFO] Switched to wlan0 as the default route" >> "$LOGFILE"
  if ! ip route | grep -q "^default via $gateway "; then
      ip route del default dev wlan0 2>/dev/null   #delete the old settings      
      ip route add default via "$gateway" dev wlan0 metric 10 2>/dev/null
  fi
  
fi
