#!/bin/sh

WIFI_LED="/sys/class/leds/JA35/brightness"
LTE_LED="/sys/class/leds/JA33/brightness"

WIFI_IF="wlan0"
LTE_IF="ppp0"

BLINK_ON=1
BLINK_OFF=0
CHECK_INTERVAL=1
BLINK_DURATION=0.1

# Initialize previous byte counters
prev_tx=0
prev_rx=0

while true; do
    DEFAULT_IF=$(ip route | awk '/^default/ {for (i=1;i<=NF;i++) if ($i=="dev") print $(i+1); exit}')

    if [ -n "$DEFAULT_IF" ]; then
        # Choose LED based on default interface
        if [ "$DEFAULT_IF" = "$WIFI_IF" ]; then
            LED=$WIFI_LED
        elif [ "$DEFAULT_IF" = "$LTE_IF" ]; then
            LED=$LTE_LED
        else
            LED=""
        fi

        # Turn off both LEDs, then activate only the default one
        echo $BLINK_OFF > "$WIFI_LED"
        echo $BLINK_OFF > "$LTE_LED"

        if [ -n "$LED" ]; then
            tx=$(cat /sys/class/net/$DEFAULT_IF/statistics/tx_bytes)
            rx=$(cat /sys/class/net/$DEFAULT_IF/statistics/rx_bytes)

            if [ "$tx" -ne "$prev_tx" ] || [ "$rx" -ne "$prev_rx" ]; then
                # Traffic flowing — custom blink
                echo $BLINK_ON > "$LED"
                sleep $BLINK_DURATION
                echo $BLINK_OFF > "$LED"
                sleep $BLINK_DURATION
                echo $BLINK_ON > "$LED"
                sleep $BLINK_DURATION
                echo $BLINK_OFF > "$LED"
                sleep $BLINK_DURATION
            else
                # No traffic — solid LED
                echo $BLINK_ON > "$LED"
                sleep $CHECK_INTERVAL
            fi

            prev_tx=$tx
            prev_rx=$rx
        fi
    else
        # ❗ No default route = No internet — blink once per second
        echo $BLINK_OFF > "$WIFI_LED"
        echo $BLINK_OFF > "$LTE_LED"
        sleep $BLINK_DURATION
        echo $BLINK_ON > "$WIFI_LED"
        echo $BLINK_ON > "$LTE_LED"
        sleep $BLINK_DURATION
        echo $BLINK_OFF > "$WIFI_LED"
        echo $BLINK_OFF > "$LTE_LED"
        sleep $CHECK_INTERVAL
    fi
done
