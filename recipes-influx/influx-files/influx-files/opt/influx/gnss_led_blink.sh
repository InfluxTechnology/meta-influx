#!/bin/bash

LED_PATH="/sys/class/leds/JB12/brightness"

# Blink 3 times
for i in {1..2}
do
    echo 0 > "$LED_PATH"
    sleep 0.1
    echo 1 > "$LED_PATH"
    sleep 0.1
done
