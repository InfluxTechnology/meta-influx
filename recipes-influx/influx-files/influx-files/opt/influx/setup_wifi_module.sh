#!/bin/sh
#set -ex

echo 0 > /sys/block/mmcblk2boot0/force_ro
switch_module.sh 1MW
/sbin/fw_printenv fdt_file imx8mm-influx-rex-smart_v2-1mw.dtb
sync
reboot
