#!/bin/sh

# start LTE connection by wvdial

/opt/influx/ublox-up-down-pin.sh
wvdial '1nce' 2> '/tmp/3G_1nce.log' &

# NOTE: we can view process of the connection with: tail -f /tmp/3G_1nce.log
# can test connection with: ping -I ppp0 8.8.8.8
# to stop wvdial exec command
# killall wvdial
