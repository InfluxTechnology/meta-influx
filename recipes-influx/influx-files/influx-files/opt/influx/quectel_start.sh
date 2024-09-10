#!/usr/bin/env bash

echo 0 > /sys/class/leds/lte_VCC/brightness           # JB02 - VCC            reverce logic
echo 0 > /sys/class/leds/lte_PWR_ON/brightness        # JB14 - RWR_ON
echo 0 > /sys/class/leds/lte_RESET/brightness         # JB08 - RESET
sleep 0.01
echo 1 > /sys/class/leds/lte_VCC/brightness
echo 1 > /sys/class/leds/lte_PWR_ON/brightness
echo 1 > /sys/class/leds/lte_RESET/brightness
sleep 0.04
echo 0 > /sys/class/leds/lte_PWR_ON/brightness
sleep 0.6
echo 1 > /sys/class/leds/lte_PWR_ON/brightness
