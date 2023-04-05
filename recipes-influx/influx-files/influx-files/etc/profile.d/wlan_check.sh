#!/bin/sh

# check status of  wlan0.service
wlan0_active=$(systemctl is-active wpa_supplicant@wlan0.service)
if [ "$wlan0_active" == "inactive" ];
then
    echo -e "\e[32;1mInfo:\e[0m \e[32m To enable wlan support service, start manually these commands. \e[0m"
    echo -e "\e[32m		switch_module.sh 1MW \e[0m"
    echo -e "\e[32m		fw_setenv fdt_file imx8mm-ea-ucom-kit_v2-1mw.dtb \e[0m"
    echo -e "\e[32m		reboot \e[0m"
    echo ""	
fi
