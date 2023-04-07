#!/bin/sh

echo 0 > /sys/class/gpio/gpio9/value
echo 0 > /sys/class/gpio/gpio6/value
sleep 1
echo 1 > /sys/class/gpio/gpio6/value
sleep 1
echo 1 > /sys/class/gpio/gpio9/value
