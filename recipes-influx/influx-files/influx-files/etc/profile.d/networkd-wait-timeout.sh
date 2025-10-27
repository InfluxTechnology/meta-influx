#!/bin/sh

# editing this service unit with timeout 10s (default is 2 mins).
SNWOS="/usr/lib/systemd/system/systemd-networkd-wait-online.service"
TIME_OUT=$(cat "$SNWOS" | grep 'ExecStart=/usr/lib/systemd/systemd-networkd-wait-online --timeout=10')
if [[ "$TIME_OUT" == "" ]]; then
    /bin/sed -i "s/systemd-networkd-wait-online.service/systemd_networkd_wait_online.service/" "$SNWOS"
    /bin/sed -i "s/systemd-networkd-wait-online/systemd-networkd-wait-online --timeout=10/" "$SNWOS"
fi
