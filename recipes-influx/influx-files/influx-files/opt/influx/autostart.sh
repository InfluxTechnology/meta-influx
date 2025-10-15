#!/bin/sh

# Power up the Quectel chip
/opt/influx/cellular_module_start.sh

# start LTE connection by wvdial
#/opt/influx/lte_start_wvdial.sh
#/opt/influx/start_ppp0.sh

echo 0 > /sys/block/mmcblk2boot0/force_ro

systemctl stop serial-getty@ttymxc1.service
systemctl disable serial-getty@ttymxc1.service

