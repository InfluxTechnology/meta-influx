#!/bin/sh

# keep tailscale status
TA=$(systemctl is-active tailscaled)
fw_setenv tailscale_actile "$TA"
TE=$(systemctl is-enabled tailscaled)
fw_setenv tailscale_enabled "$TE"

# keep time zone
TZ=$(/usr/bin/timedatectl | grep 'Time zone' | cut -d : -f 2 | cut -d ' ' -f 2)
fw_setenv time_zone "$TZ"
