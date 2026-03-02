#!/bin/sh
# LED Blink Script - Shows network status via LEDs
# WiFi LED (JA35) - blinks when WiFi is default route
# LTE LED (JA33) - blinks when LTE is default route

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

get_default_if() {
    # Read /proc/net/route directly - no process spawns
    # Fields: Iface Destination Gateway ... (tab-separated)
    # Default route has Destination=00000000
    while IFS='	' read -r iface dest _; do
        if [ "$dest" = "00000000" ]; then
            echo "$iface"
            return
        fi
    done < /proc/net/route
}

read_stat() {
    read -r val < "$1" 2>/dev/null
    echo "${val:-0}"
}

while true; do
    DEFAULT_IF=$(get_default_if)

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
            tx=$(read_stat /sys/class/net/$DEFAULT_IF/statistics/tx_bytes)
            rx=$(read_stat /sys/class/net/$DEFAULT_IF/statistics/rx_bytes)

            if [ "$tx" != "$prev_tx" ] || [ "$rx" != "$prev_rx" ]; then
                # Traffic flowing - double blink then wait
                echo $BLINK_ON > "$LED"
                sleep $BLINK_DURATION
                echo $BLINK_OFF > "$LED"
                sleep $BLINK_DURATION
                echo $BLINK_ON > "$LED"
                sleep $BLINK_DURATION
                echo $BLINK_OFF > "$LED"
                sleep $CHECK_INTERVAL
            else
                # No traffic - solid LED
                echo $BLINK_ON > "$LED"
                sleep $CHECK_INTERVAL
            fi

            prev_tx=$tx
            prev_rx=$rx
        else
            sleep $CHECK_INTERVAL
        fi
    else
        # No default route = No internet - blink both LEDs slowly
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
