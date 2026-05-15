#!/bin/sh
#
# Install/update ReXgen network services
# Handles: old->new migration, new->new redeploy
#

DEST="/opt/influx/netservices"
OLD_DEST="/opt/influx/ap_flask"

# New service names
NEW_SERVICES="wifi-manager wifi-dashboard led-blink"
# Old/legacy service names to look for
OLD_SERVICES="wifi_monitor"

echo "========================================"
echo "  ReXgen Network Services Installer"
echo "========================================"
echo "Install source : $DEST"
echo "Old install dir : $OLD_DEST"
echo ""

# -------------------------------------------------------
# Phase 1: Detect existing installations
# -------------------------------------------------------
echo "--- Phase 1: Detecting existing installations ---"

FOUND_OLD=0
FOUND_NEW=0

# Check for old legacy services
for svc in $OLD_SERVICES; do
    if systemctl list-unit-files "${svc}.service" 2>/dev/null | grep -q "$svc"; then
        echo "  [FOUND] Old service unit: ${svc}.service"
        FOUND_OLD=1
    elif [ -f "/etc/systemd/system/${svc}.service" ]; then
        echo "  [FOUND] Old service file:  /etc/systemd/system/${svc}.service"
        FOUND_OLD=1
    else
        echo "  [  OK ] Old service ${svc} not present"
    fi
done

# Check for old ap_flask directory
if [ -d "$OLD_DEST" ]; then
    echo "  [FOUND] Old install dir:   $OLD_DEST"
    FOUND_OLD=1
else
    echo "  [  OK ] Old install dir not present"
fi

# Check for orphaned ap_flask.py processes
OLD_PIDS=$(ps | grep 'ap_flask.py' | grep -v grep | awk '{print $1}')
if [ -n "$OLD_PIDS" ]; then
    echo "  [FOUND] Old ap_flask.py running (PIDs: $OLD_PIDS)"
    FOUND_OLD=1
else
    echo "  [  OK ] No orphaned ap_flask.py processes"
fi

# Check for current (new) services already installed
for svc in $NEW_SERVICES; do
    if systemctl list-unit-files "${svc}.service" 2>/dev/null | grep -q "$svc"; then
        echo "  [FOUND] Existing service:  ${svc}.service"
        FOUND_NEW=1
    elif [ -f "/etc/systemd/system/${svc}.service" ]; then
        echo "  [FOUND] Existing service file: /etc/systemd/system/${svc}.service"
        FOUND_NEW=1
    else
        echo "  [  OK ] Service ${svc} not yet installed"
    fi
done

echo ""
if [ "$FOUND_OLD" = "1" ] && [ "$FOUND_NEW" = "1" ]; then
    echo "  => Both old and new installations detected. Will clean up old + redeploy new."
elif [ "$FOUND_OLD" = "1" ]; then
    echo "  => Old installation detected. Will migrate to new services."
elif [ "$FOUND_NEW" = "1" ]; then
    echo "  => Existing new installation detected. Will redeploy/update."
else
    echo "  => Fresh install."
fi
echo ""

# -------------------------------------------------------
# Phase 2: Uninstall old/legacy services
# -------------------------------------------------------
echo "--- Phase 2: Removing old/legacy services ---"

for svc in $OLD_SERVICES; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        echo "  Stopping old service: $svc ..."
        systemctl stop "$svc"
        echo "  Stopped $svc."
    fi
    if systemctl is-enabled --quiet "$svc" 2>/dev/null; then
        echo "  Disabling old service: $svc ..."
        systemctl disable "$svc" 2>/dev/null || true
        echo "  Disabled $svc."
    fi
    if [ -f "/etc/systemd/system/${svc}.service" ]; then
        echo "  Removing unit file: /etc/systemd/system/${svc}.service"
        rm -f "/etc/systemd/system/${svc}.service"
        echo "  Removed."
    fi
done

# Kill orphaned ap_flask.py processes
if [ -n "$OLD_PIDS" ]; then
    echo "  Killing old ap_flask.py processes (PIDs: $OLD_PIDS) ..."
    kill $OLD_PIDS 2>/dev/null || true
    sleep 1
    # Verify they're gone
    REMAINING=$(ps | grep 'ap_flask.py' | grep -v grep | awk '{print $1}')
    if [ -n "$REMAINING" ]; then
        echo "  [WARN] Processes still alive, sending SIGKILL ..."
        kill -9 $REMAINING 2>/dev/null || true
    fi
    echo "  Old processes cleaned up."
else
    echo "  No old processes to kill."
fi

# Remove old install directory
if [ -d "$OLD_DEST" ]; then
    echo "  Removing old directory: $OLD_DEST ..."
    rm -rf "$OLD_DEST"
    echo "  Removed."
else
    echo "  Old directory not present, nothing to remove."
fi

echo "  Phase 2 complete."
echo ""

# -------------------------------------------------------
# Phase 3: Stop current services (for redeploy)
# -------------------------------------------------------
echo "--- Phase 3: Stopping current services ---"

for svc in $NEW_SERVICES; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        echo "  Stopping $svc ..."
        systemctl stop "$svc"
        echo "  Stopped."
    else
        echo "  $svc not running, skip."
    fi
done

echo "  Phase 3 complete."
echo ""

# -------------------------------------------------------
# Phase 4: System setup
# -------------------------------------------------------
echo "--- Phase 4: System setup ---"

echo "  Creating /tmp/rexgen ..."
mkdir -p /tmp/rexgen
echo "  Creating /var/run/wpa_supplicant ..."
mkdir -p /var/run/wpa_supplicant

echo "  Stopping any running wpa_supplicant ..."
killall wpa_supplicant 2>/dev/null || true

# Ensure wpa_supplicant config has ctrl_interface header
if [ ! -f /etc/wpa_supplicant.conf ]; then
    echo "  [WARN] /etc/wpa_supplicant.conf not found, creating fresh config ..."
    echo "ctrl_interface=/var/run/wpa_supplicant" > /etc/wpa_supplicant.conf
    echo "update_config=1" >> /etc/wpa_supplicant.conf
    echo "" >> /etc/wpa_supplicant.conf
    echo "  Created /etc/wpa_supplicant.conf"
elif ! grep -q "ctrl_interface" /etc/wpa_supplicant.conf; then
    echo "  [WARN] ctrl_interface missing from wpa_supplicant.conf, prepending header ..."
    echo "ctrl_interface=/var/run/wpa_supplicant" > /tmp/wpa_header
    echo "update_config=1" >> /tmp/wpa_header
    echo "" >> /tmp/wpa_header
    cat /etc/wpa_supplicant.conf >> /tmp/wpa_header
    mv /tmp/wpa_header /etc/wpa_supplicant.conf
    echo "  Updated /etc/wpa_supplicant.conf"
else
    echo "  wpa_supplicant.conf already has ctrl_interface, OK."
fi

echo "  Setting scripts executable ..."
chmod +x "$DEST/scripts/"*.sh 2>/dev/null || true

echo "  Phase 4 complete."
echo ""

# -------------------------------------------------------
# Phase 5: Deploy SSL CA certificate
# -------------------------------------------------------
echo "--- Phase 5: Deploying SSL CA certificate ---"

SSL_DEST="/data/rexgen/config/ssl"
SSL_SRC="$DEST/ssl"

mkdir -p "$SSL_DEST"
chmod 700 "$SSL_DEST"

if [ -f "$SSL_SRC/ca.crt" ] && [ -f "$SSL_SRC/ca.key" ]; then
    echo "  Copying CA certificate and key to $SSL_DEST ..."
    cp "$SSL_SRC/ca.crt" "$SSL_DEST/ca.crt"
    cp "$SSL_SRC/ca.key" "$SSL_DEST/ca.key"
    # Force server certificate re-issue from the currently deployed CA.
    rm -f "$SSL_DEST/dashboard.crt" "$SSL_DEST/dashboard.key"
    chmod 644 "$SSL_DEST/ca.crt"
    chmod 600 "$SSL_DEST/ca.key"
    echo "  CA deployed."
else
    echo "  [WARN] ssl/ca.crt or ssl/ca.key not found in $SSL_SRC — HTTPS will not work!"
fi

echo "  Phase 5 complete."
echo ""

# -------------------------------------------------------
# Phase 6: Install and activate services
# -------------------------------------------------------
echo "--- Phase 6: Installing service files ---"

if [ ! -d "$DEST/systemd" ]; then
    echo "  [ERROR] $DEST/systemd/ not found! Cannot install service files."
    exit 1
fi

for f in "$DEST/systemd/"*.service; do
    if [ -f "$f" ]; then
        echo "  Copying $(basename "$f") -> /etc/systemd/system/"
        cp "$f" /etc/systemd/system/
    fi
done

# Ensure wlan0 is not managed by systemd-networkd DHCP (netservices owns DHCP via udhcpc).
if [ -f "$DEST/systemd/20-wireless-wlan0.network" ]; then
    echo "  Copying 20-wireless-wlan0.network -> /etc/systemd/network/"
    mkdir -p /etc/systemd/network
    cp "$DEST/systemd/20-wireless-wlan0.network" /etc/systemd/network/20-wireless-wlan0.network
    echo "  Restarting systemd-networkd ..."
    systemctl restart systemd-networkd 2>/dev/null || echo "  [WARN] Failed to restart systemd-networkd"
fi

echo "  Reloading systemd daemon ..."
systemctl daemon-reload

echo "  Enabling services ..."
for svc in wpa_supplicant@wlan0 $NEW_SERVICES; do
    echo "    enable $svc"
    systemctl enable "$svc" 2>/dev/null || echo "    [WARN] Failed to enable $svc"
done

echo "  Starting services ..."
for svc in wpa_supplicant@wlan0 $NEW_SERVICES; do
    echo "    restart $svc ..."
    systemctl restart "$svc" 2>/dev/null
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        echo "    $svc -> active"
    else
        echo "    [WARN] $svc -> NOT active (check: journalctl -u $svc)"
    fi
done

echo ""
echo "========================================"
echo "  Installation complete"
echo "========================================"
echo ""
echo "Service status:"
for svc in wpa_supplicant@wlan0 $NEW_SERVICES; do
    STATUS=$(systemctl is-active "$svc" 2>/dev/null || echo "unknown")
    printf "  %-25s %s\n" "$svc" "$STATUS"
done
echo ""
echo "Troubleshooting: journalctl -u <service-name> -n 50"
