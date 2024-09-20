#!/bin/bash

# Start PPP connection
echo "Starting PPP connection..."
pppd call quectel-ppp &

# Wait for ppp0 to come up (up to 15 seconds)
TIMEOUT=15
while ! ip a show ppp0 | grep -q "inet"; do
    sleep 1
    TIMEOUT=$((TIMEOUT-1))
    if [ $TIMEOUT -le 0 ]; then
        echo "Error: ppp0 did not come up within 15 seconds."
        exit 1
    fi
done

# Display ppp0 IP address
IPADDR=$(ip -4 -o addr show ppp0 | awk '{print $4}')
echo "PPP connection established. ppp0 IP address: $IPADDR"

# Test Internet connectivity through ppp0 (pinging Google's DNS server)
echo "Testing Internet connectivity through ppp0..."
if ping -I ppp0 -c 4 8.8.8.8 > /dev/null 2>&1; then
    echo "Internet connection through ppp0 is working."
else
    echo "Error: No Internet connection on ppp0."
    exit 1
fi
