#!/bin/sh

/opt/influx/rexgen_sn_to_hostname.sh
/usr/bin/systemctl restart avahi-daemon.service

/opt/influx/check_taiscale_status.sh

# update timedatectl service
TZ=$(fw_printenv time_zone | cut -d = -f 2)
if [ "$TZ" != "" ]; then
    timedatectl set-timezone "$TZ"
fi
systemctl restart systemd-timesyncd.service

/usr/bin/systemctl start end_influx_upgrade.service &
