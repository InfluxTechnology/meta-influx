#!/bin/sh

if [ -f /opt/influx/wpa_supplicant.conf.cust ]; then
    mv /opt/influx/wpa_supplicant.conf.cust /etc/wpa_supplicant.conf
fi
