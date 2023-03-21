#!/bin/sh

#modprobe -r rexgen_usb
#depmod -a
modprobe rexgen_usb

dmesg -C
#power off/on USB to load rexgen_usb driver
/usr/local/bin/uhubctl -a off -p 1 -l 1
/usr/local/bin/uhubctl -a on -p 1 -l 1

ip link set can0 type can bitrate 500000
ip link set up can0

dmesg | grep RexGen

