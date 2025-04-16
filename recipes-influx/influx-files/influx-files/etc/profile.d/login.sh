#!/bin/sh

# move old BT firm ware
#if [ -f /etc/firmware/BCM4345C0_003.001.025.0144.0266.1MW.hcd ]; then
#    mv /etc/firmware/BCM4345C0_003.001.025.0144.0266.1MW.hcd /etc/firmware/murata-master/_BCM4345C0_003.001.025.0144.0266.1MW.hcd
#fi

# prepare config files for LTE communication
#if test -f /opt/influx/options; then
#    mv /opt/influx/options /etc/ppp/
#    mv /opt/influx/pap-secrets /etc/ppp/
#fi

# crontab uses this editor
EDITOR=nano	

# editing this service unit with timeout 10s (default is 2 mins).
SNWOS="/lib/systemd/system/systemd-networkd-wait-online.service"
TIME_OUT=$(cat "$SNWOS" | grep 'ExecStart=/lib/systemd/systemd-networkd-wait-online --timeout=10')
if [[ "$TIME_OUT" == "" ]]; then
    /bin/sed -i "s/systemd-networkd-wait-online.service/systemd_networkd_wait_online.service/" "$SNWOS"
    /bin/sed -i "s/systemd-networkd-wait-online/systemd-networkd-wait-online --timeout=10/" "$SNWOS"
fi

 # check for new firmware version
# /opt/influx/check_firmware_version.sh 1
