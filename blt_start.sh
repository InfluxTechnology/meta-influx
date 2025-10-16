#!/bin/sh

hciattach /dev/ttymxc0 bcm43xx 3000000 flow -t 20
hciconfig hci0 up

bluetoothctl power on
bluetoothctl agent on
bluetoothctl default-agent
bluetoothctl discoverable on
bluetoothctl pairable on


