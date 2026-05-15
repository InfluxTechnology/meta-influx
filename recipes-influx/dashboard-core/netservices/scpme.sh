#!/bin/bash
#
# Deploy network services to ReXgen device
#

IP=${1:-192.168.11.147}
PASS=${2:-pass}
DEST="/opt/influx/netservices"

OPTS="-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"

echo "Deploying to $IP:$DEST ..."

# Copy files to device
sshpass -p "$PASS" ssh $OPTS root@"$IP" "mkdir -p $DEST"
sshpass -p "$PASS" scp $OPTS -r services/ dashboard/ systemd/ scripts/ ssl/ install.sh root@"$IP":$DEST/

# Copy systemd units to system folder
sshpass -p "$PASS" scp $OPTS systemd/*.service root@"$IP":/etc/systemd/system/

# Run install on device
sshpass -p "$PASS" ssh $OPTS root@"$IP" "chmod +x $DEST/install.sh && $DEST/install.sh"
