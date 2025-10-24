#!/bin/sh

# create link to rexgen tool
if [ ! -f /usr/sbin/rexgen ]; then
    ln -s /home/root/rexusb/rexgen /usr/sbin/rexgen
fi

# create link to aws tool
if [ ! -f /usr/sbin/aws ]; then
    ln -s /home/root/rexusb/aws /usr/sbin/aws
fi

