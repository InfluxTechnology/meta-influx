#!/bin/sh

# keep tailscale status
if [ $(fw_printenv tailscale_actile | cut -d = -f 2) == "active" ]; then
    systemctl start tailscaled
else
    systemctl stop tailscaled
fi

if [ $(fw_printenv tailscale_enabled | cut -d = -f 2) == "enabled" ]; then
    systemctl enable tailscaled
else
    systemctl disable tailscaled
fi
