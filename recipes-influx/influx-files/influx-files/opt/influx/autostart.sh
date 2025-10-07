#!/bin/sh

export EDITOR=/usr/bin/nano	# crontab uses this editor
# execute at first time
/etc/profile.d/enable_services.sh

# Power up the Quectel chip
/opt/influx/cellular_module_start.sh

# start LTE connection by wvdial
#/opt/influx/lte_start_wvdial.sh
#/opt/influx/start_ppp0.sh

echo 0 > /sys/block/mmcblk2boot0/force_ro
