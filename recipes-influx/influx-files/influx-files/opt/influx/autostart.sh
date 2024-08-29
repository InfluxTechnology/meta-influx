#!/bin/sh

EDITOR=nano	# crontab uses this editor

# Power up the Quectel chip
/opt/influx/quectel_start.sh

# start LTE connection by wvdial
#/opt/influx/lte_start_wvdial.sh


# load to RexGen proper configuration
/home/root/rexusb/rexgen configure /home/root/rexusb/config/Structure_v7_gnss.rxc

