#!/bin/sh

if test -f /home/root/rexusb/var/serial_short && test -f /opt/influx/release; then
        SHORT_SN=$(cat /home/root/rexusb/var/serial_short)
        INFL_REL=$(cat /opt/influx/release)
        INFL_REL=$(echo "${INFL_REL//.}")
        INFL_REL=$(echo "${INFL_REL//_}")

        echo $INFL_REL"-SN"$SHORT_SN > /etc/hostname
        sed -i 's/\_/\-/g' /etc/hostname
fi
