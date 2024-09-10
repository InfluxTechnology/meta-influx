#!/bin/sh

/sbin/modprobe -r rexgen_usb
/sbin/modprobe -r can_raw
/sbin/modprobe -r can

/home/root/rexusb/rexgen configure /home/root/rexusb/config/Structure_v7_gnss.rxc
