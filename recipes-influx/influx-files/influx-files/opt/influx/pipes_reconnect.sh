#!/bin/sh

/sbin/modprobe -r rexgen_usb
/sbin/modprobe -r can_raw
/sbin/modprobe -r can

/home/root/rexusb/rexgen configure /home/root/rexusb/config/Smart_v1.rxc
