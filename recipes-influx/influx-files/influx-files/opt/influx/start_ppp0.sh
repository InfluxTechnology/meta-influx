#!/bin/sh

# Log function to append timestamp and message to /var/log/lte_ppp.log
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> /var/log/lte_ppp.log
}

# Start PPP connection
log "Starting PPP connection..."
echo "Starting PPP connection..." | logger

pppd call quectel-ppp &

# Wait for ppp0 to come up (up to 15 seconds)
TIMEOUT=15
while ! ip a show ppp0 | grep -q "inet"; do
    sleep 1
    TIMEOUT=$((TIMEOUT-1))
    if [ $TIMEOUT -le 0 ]; then
        log "Error: ppp0 did not come up within 15 seconds."
        echo "Error: ppp0 did not come up within 15 seconds." | logger
        exit 1
    fi
done

# Retrieve the IP address assigned to ppp0
IPADDR=$(ip -4 -o addr show ppp0 | awk '{print $4}')
log "PPP connection established. ppp0 IP address: $IPADDR"
echo "PPP connection established. ppp0 IP address: $IPADDR" | logger

# Test Internet connectivity through ppp0 (ping Google's DNS server)
log "Testing Internet connectivity through ppp0..."
echo "Testing Internet connectivity through ppp0..." | logger

if ping -I ppp0 -c 4 8.8.8.8 > /dev/null 2>&1; then
    log "Internet connection through ppp0 is working."
    echo "Internet connection through ppp0 is working." | logger
else
    log "Error: No Internet connection on ppp0."
    echo "Error: No Internet connection on ppp0." | logger
    exit 1
fi

# Log successful PPP connection with assigned IP address
log "PPP connection with IP address $IPADDR is fully established and functional."
echo "PPP connection with IP address $IPADDR is fully established and functional." | logger
