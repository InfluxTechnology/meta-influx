#!/bin/bash

LOG_FILE="/var/log/wifi_monitor.log"
AP_FLASK_PID_FILE="/var/run/ap_flask.pid"

check_wifi_connection() {
    # Check if wlan0 is connected to a Wi-Fi network
    connection_status=$(iw wlan0 link | grep "Connected to")
    if [ -n "$connection_status" ]; then
        return 0  # Connected
    else
        return 1  # Not connected
    fi
}

check_network_availability() {
    # Check if a previously saved network is now available
    saved_ssid=$(grep ssid= /etc/wpa_supplicant.conf | head -1 | cut -d'"' -f2)
    if [ -n "$saved_ssid" ]; then
        available_network=$(iw wlan0 scan 2>/dev/null | grep "SSID: $saved_ssid")
        if [ -n "$available_network" ]; then
            echo "$(date) - Saved network $saved_ssid is now available." >> "$LOG_FILE"
            return 0  # Network available
        fi
    fi
    return 1  # Network not available
}

start_ap_flask() {
    if [ -f "$AP_FLASK_PID_FILE" ]; then
        ap_flask_pid=$(cat "$AP_FLASK_PID_FILE")
        if ps -p "$ap_flask_pid" > /dev/null 2>&1; then
            echo "$(date) - AP Flask is already running with PID $ap_flask_pid. Skipping start..." >> "$LOG_FILE"
            return
        else
            echo "$(date) - Cleaning up stale AP Flask PID file." >> "$LOG_FILE"
            rm -f "$AP_FLASK_PID_FILE"
        fi
    fi
    echo "$(date) - Starting AP Flask mode..." >> "$LOG_FILE"
    /usr/bin/python3 /opt/influx/ap_flask/ap_flask.py &
    echo $! > "$AP_FLASK_PID_FILE"
    echo "$(date) - AP Flask mode started with PID $(cat $AP_FLASK_PID_FILE)." >> "$LOG_FILE"
}

stop_ap_flask() {
    if [ -f "$AP_FLASK_PID_FILE" ]; then
        ap_flask_pid=$(cat "$AP_FLASK_PID_FILE")
        if ps -p "$ap_flask_pid" > /dev/null 2>&1; then
            echo "$(date) - Stopping AP Flask mode with PID $ap_flask_pid..." >> "$LOG_FILE"
            kill "$ap_flask_pid"
            rm -f "$AP_FLASK_PID_FILE"
            echo "$(date) - AP Flask mode stopped." >> "$LOG_FILE"
        else
            echo "$(date) - AP Flask process not running. Cleaning up PID file." >> "$LOG_FILE"
            rm -f "$AP_FLASK_PID_FILE"
        fi
    else
        echo "$(date) - No AP Flask instances found to stop." >> "$LOG_FILE"
    fi
}

attempt_connection() {
    echo "$(date) - Attempting to connect to saved Wi-Fi network..." >> "$LOG_FILE"
    systemctl restart wpa_supplicant@wlan0.service
    sleep 10
    check_wifi_connection
    return $?
}

main() {
    ATTEMPT_COUNT=0
    MAX_ATTEMPTS=3
    AP_MODE_ACTIVE=false

    while true; do
        check_wifi_connection
        if [ $? -eq 0 ]; then
            echo "$(date) - Wi-Fi is connected. Checking AP Flask mode..." >> "$LOG_FILE"
            if [ "$AP_MODE_ACTIVE" = true ]; then
                stop_ap_flask
                AP_MODE_ACTIVE=false
            fi
            ATTEMPT_COUNT=0
        else
            if [ "$AP_MODE_ACTIVE" = false ]; then
                if [ $ATTEMPT_COUNT -lt $MAX_ATTEMPTS ]; then
                    echo "$(date) - No Wi-Fi connection detected. Attempting to connect..." >> "$LOG_FILE"
                    attempt_connection
                    if [ $? -eq 0 ]; then
                        echo "$(date) - Wi-Fi connected successfully." >> "$LOG_FILE"
                        ATTEMPT_COUNT=0
                    else
                        ATTEMPT_COUNT=$((ATTEMPT_COUNT + 1))
                        echo "$(date) - Connection attempt $ATTEMPT_COUNT/$MAX_ATTEMPTS failed." >> "$LOG_FILE"
                    fi
                else
                    echo "$(date) - Maximum connection attempts reached. Starting AP Flask mode..." >> "$LOG_FILE"
                    start_ap_flask
                    AP_MODE_ACTIVE=true
                fi
            else
                check_network_availability
                if [ $? -eq 0 ]; then
                    echo "$(date) - Previously connected network is available. Stopping AP Flask and connecting..." >> "$LOG_FILE"
                    stop_ap_flask
                    AP_MODE_ACTIVE=false
                    ATTEMPT_COUNT=0
                    attempt_connection
                else
                    echo "$(date) - AP Flask mode is already active. Skipping new connection attempts..." >> "$LOG_FILE"
                fi
            fi
        fi
        sleep 30
    done
}

main
