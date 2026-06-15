#!/bin/sh
#
# Install/update ReXgen network services - lite (Wi-Fi only)
#

DEST="/opt/influx/netservices-lite"
SERVICES="wifi-manager wifi-dashboard led-blink"

echo "========================================"
echo "  ReXgen Network Services Installer (lite)"
echo "========================================"
echo "Install source : $DEST"
echo ""

# Phase 1: Stop currently installed services
echo "--- Phase 1: Stopping current services ---"
for svc in $SERVICES; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        echo "  Stopping $svc ..."
        systemctl stop "$svc"
    else
        echo "  $svc not running, skip."
    fi
done
echo ""

# Phase 2: System setup
echo "--- Phase 2: System setup ---"
mkdir -p /data/rexgen/tmp /data/rexgen/config
mkdir -p /var/run/wpa_supplicant
killall wpa_supplicant 2>/dev/null || true

if [ ! -f /etc/wpa_supplicant.conf ]; then
    echo "  Creating fresh /etc/wpa_supplicant.conf ..."
    {
        echo "ctrl_interface=/var/run/wpa_supplicant"
        echo "update_config=1"
        echo ""
    } > /etc/wpa_supplicant.conf
elif ! grep -q "ctrl_interface" /etc/wpa_supplicant.conf; then
    echo "  Prepending ctrl_interface header to wpa_supplicant.conf ..."
    {
        echo "ctrl_interface=/var/run/wpa_supplicant"
        echo "update_config=1"
        echo ""
        cat /etc/wpa_supplicant.conf
    } > /tmp/wpa_header
    mv /tmp/wpa_header /etc/wpa_supplicant.conf
fi

chmod +x "$DEST/scripts/"*.sh 2>/dev/null || true
echo ""

# Phase 3: Install service files
echo "--- Phase 3: Installing service files ---"
if [ ! -d "$DEST/systemd" ]; then
    echo "  [ERROR] $DEST/systemd/ not found!"
    exit 1
fi
for f in "$DEST/systemd/"*.service; do
    [ -f "$f" ] && cp "$f" /etc/systemd/system/
done
if [ -f "$DEST/systemd/20-wireless-wlan0.network" ]; then
    mkdir -p /etc/systemd/network
    cp "$DEST/systemd/20-wireless-wlan0.network" /etc/systemd/network/20-wireless-wlan0.network
    systemctl restart systemd-networkd 2>/dev/null || true
fi
systemctl daemon-reload

for svc in wpa_supplicant@wlan0 $SERVICES; do
    systemctl enable "$svc" 2>/dev/null || echo "  [WARN] enable $svc failed"
done
for svc in wpa_supplicant@wlan0 $SERVICES; do
    systemctl restart "$svc" 2>/dev/null
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        echo "  $svc -> active"
    else
        echo "  [WARN] $svc -> NOT active (journalctl -u $svc)"
    fi
done

echo ""
echo "========================================"
echo "  Installation complete"
echo "========================================"
for svc in wpa_supplicant@wlan0 $SERVICES; do
    STATUS=$(systemctl is-active "$svc" 2>/dev/null || echo "unknown")
    printf "  %-25s %s\n" "$svc" "$STATUS"
done
