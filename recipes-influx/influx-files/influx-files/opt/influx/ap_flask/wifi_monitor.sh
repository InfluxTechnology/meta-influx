#!/bin/sh

# ================================
# Wi-Fi Monitoring and AP Control
# ================================

LOG_FILE="/var/log/wifi_monitor.log"

# Function to start the AP Flask mode
start_ap_flask() {
    if pgrep -f ap_flask.py > /dev/null; then
        echo "$(date) - AP Flask is already running. Skipping start..." >> "$LOG_FILE"
        return
    fi

    echo "$(date) - Starting AP Flask mode..." >> "$LOG_FILE"
    /usr/bin/python3 /opt/influx/ap_flask/ap_flask.py &
    echo "$(date) - AP Flask mode started" >> "$LOG_FILE"
}

main() {
    ATTEMPT_COUNT=0
    MAX_ATTEMPTS=3
    AP_MODE_ACTIVE=false

    start_ap_flask
    exit 0
}

main
