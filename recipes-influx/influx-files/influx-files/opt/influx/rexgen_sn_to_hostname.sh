#!/bin/sh

if test -f /home/root/rexusb/var/serial; then
        SN=$(cat /home/root/rexusb/var/serial)
	SN=$(echo "$SN" | sed 's/_/-/g')

	hostnamectl hostname $SN
fi
