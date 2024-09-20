#!/bin/sh

LSUSB=$(lsusb)

if echo $LSUSB  | grep -q "Quectel"; then
        /opt/influx/gnssinit_quectel.py
fi

if echo $LSUSB  | grep -q "U-Blox"; then
        /opt/influx/gnssinit_ublox.py
fi

