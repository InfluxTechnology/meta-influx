#!/bin/sh

# Influx RexGen system log service
if test -f /opt/influx/rex_sys_log.sh; then
    mv /opt/influx/rex_sys_log.* /home/root/rexusb/log/
    systemctl enable rex_sys_log.service
    systemctl start rex_sys_log.service 
fi

# rc.local 
if test -f /opt/influx/rc.local; then
    chmod +x /opt/influx/rc.local
    mv /opt/influx/rc.local /etc/
fi

# editing this service unit with timeout 10s (default is 2 mins).
SNWOS="/lib/systemd/system/systemd-networkd-wait-online.service"
TIME_OUT=$(cat "$SNWOS" | grep 'ExecStart=/usr/lib/systemd/systemd-networkd-wait-online --timeout=10')
if [ "$TIME_OUT" == "" ]; then
        LINE_NUM=$(grep -n 'ExecStart=/usr/lib/systemd/systemd-networkd-wait-online' "$SNWOS" | cut -d : -f 1)
        sed -i "${LINE_NUM}s/systemd-networkd-wait-online/systemd-networkd-wait-online --timeout=10/" "$SNWOS"
fi
