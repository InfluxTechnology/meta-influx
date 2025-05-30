#!/bin/sh

# check status of  wlan0.service
wlan0_active=$(systemctl is-active wpa_supplicant@wlan0.service)
if [ "$wlan0_active" == "inactive" ];
then
    /usr/sbin/switch_module.sh 1MW
    echo 0 > /sys/block/mmcblk2boot0/force_ro
    /sbin/fw_setenv fdt_file imx8mm-influx-rex-smart_v2-1mw.dtb
    sync
fi
