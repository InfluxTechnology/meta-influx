#!/bin/sh

EDITOR=nano	# crontab uses this editor

# Power up the Quectel chip
/opt/influx/cellular_module_start.sh

# start LTE connection by wvdial
#/opt/influx/lte_start_wvdial.sh


# load to RexGen proper configuration
/home/root/rexusb/rexgen configure /home/root/rexusb/config/Smart_v1.rxc

#start AP_FLASK AP MODE for this device
systemctl enable wifi_monitor.service wifi_monitor.timer
systemctl start wifi_monitor.service wifi_monitor.timer
