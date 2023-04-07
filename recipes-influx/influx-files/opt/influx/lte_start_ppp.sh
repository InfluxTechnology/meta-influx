#!/bin/sh

# start LTE connection by ppp

/opt/influx/ublox-up-down-pin.sh
/usr/bin/killall pppd 2> /dev/null
/usr/bin/pon 1nce.provider

# now connected and we have ppp0 which we can view with ifconfig
# NOTE: we can view process of the connection with tail -f /home/root/ppp-new
# to stop interface
# poff 1nce.provider


