#!/bin/sh

#echo 0 > /sys/class/gpio/gpio9/value
#echo 0 > /sys/class/gpio/gpio6/value
#sleep 1
#echo 1 > /sys/class/gpio/gpio9/value	
#echo 1 > /sys/class/gpio/gpio6/value

echo 0 > /sys/class/leds/ublox_VCC/brightness           # JB02 - VCC		reverce logic
echo 0 > /sys/class/leds/ublox_PWR_ON/brightness        # JB14 - RWR_ON
echo 0 > /sys/class/leds/ublox_RESET/brightness         # JB08 - RESET
sleep 1
echo 1 > /sys/class/leds/ublox_VCC/brightness
echo 1 > /sys/class/leds/ublox_PWR_ON/brightness
echo 1 > /sys/class/leds/ublox_RESET/brightness

