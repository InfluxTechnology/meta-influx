#!/bin/sh

# enable wlan0.service
wlan0_active=$(systemctl is-active wpa_supplicant@wlan0.service)
#if [ "$wlan0_active" == "inactive" ];
#then
#	/usr/sbin/switch_module.sh 1MW
#	sleep 3
#	/sbin/fw_setenv fdt_file imx8mm-ea-ucom-kit_v2-1mw.dtb
#fi
