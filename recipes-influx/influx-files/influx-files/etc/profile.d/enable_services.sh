#!/bin/sh

# editing this service unit with timeout 10s (default is 2 mins).
SNWOS="/lib/systemd/system/systemd-networkd-wait-online.service"
TIME_OUT=$(cat "$SNWOS" | grep 'ExecStart=/usr/lib/systemd/systemd-networkd-wait-online --timeout=10')
if [ "$TIME_OUT" == "" ]; then
        LINE_NUM=$(grep -n 'ExecStart=/usr/lib/systemd/systemd-networkd-wait-online' "$SNWOS" | cut -d : -f 1)
        sed -i "${LINE_NUM}s/systemd-networkd-wait-online/systemd-networkd-wait-online --timeout=10/" "$SNWOS"
fi
