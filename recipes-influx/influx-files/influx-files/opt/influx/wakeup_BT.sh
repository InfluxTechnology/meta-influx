#!/bin/sh

hciattach /dev/ttymxc0 bcm43xx 3000000 flow -t 20
hciconfig hci0 up

echo enabled > /sys/class/tty/ttymxc0/power/wakeup
echo 40 > /sys/class/gpio/export
echo in > /sys/class/gpio/gpio40/direction
echo 1 > /sys/class/gpio/gpio40/active_low
cat /sys/class/gpio/gpio40/value


#bluetoothctl
#power on
#agent on
#default-agent
#discoverable on
#pairable on

#hcidump > log.txt &
#echo mem > /sys/power/state
