#!/bin/sh

EDITOR=mcedit	# crontab uses this editor

# Power up the Quectel chip
/opt/influx/cellular_module_start.sh

# start LTE connection by wvdial
#/opt/influx/lte_start_wvdial.sh
#/opt/influx/start_ppp0.sh

# load to RexGen proper configuration
#/home/root/rexusb/rexgen configure /home/root/rexusb/config/Smart_v1.rxc

#start AP_FLASK AP MODE for this device
#systemctl enable wifi_monitor.service wifi_monitor.timer socket.service lte-ppp.service
#systemctl start wifi_monitor.service wifi_monitor.timer socket.service lte-ppp.service

echo 0 > /sys/block/mmcblk2boot0/force_ro