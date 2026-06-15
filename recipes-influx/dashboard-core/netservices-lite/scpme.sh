#!/bin/bash
#
# Build на готов deploy архив за netservices-lite и (опционално) качване на
# ReXgen устройство — Wi-Fi only вариант, без xoraya / rexgend / SDK bridge.
#
# Делегира build-а към scripts/pack.sh.
#
# Употреба:
#   ./scpme.sh                                    # само build на архива
#   ./scpme.sh 192.168.11.190                     # build + scp (без install)
#   ./scpme.sh 192.168.11.190 pass                # build + scp с парола "pass"
#   ./scpme.sh 192.168.11.190 pass install        # build + scp + install
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSH_OPTS="-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"

IP="${1:-}"
PASS="${2:-pass}"
ACTION="${3:-copy}"        # copy | install

# --- 1. Build pack ---------------------------------------------------------
"$ROOT_DIR/scripts/pack.sh" deploy

# --- 2. Извличане на версията за summary + scp -----------------------------
NSL_VERSION=$(awk -F'"' '/^DASHBOARD_VERSION = "/ {print $2; exit}' "$ROOT_DIR/dashboard/app.py")
NSL_ARCHIVE="$ROOT_DIR/dist/netservices-lite-${NSL_VERSION}-deploy.tar.gz"

echo
echo "=== ready ==="
printf "  %-16s %s (%s)\n" "netservices-lite" "$NSL_ARCHIVE" "$(du -h "$NSL_ARCHIVE" | awk '{print $1}')"

# --- 3. Optionally push to device ------------------------------------------
if [[ -z "$IP" ]]; then
    echo
    echo "→ no device IP given — only built the archive."
    echo "  to deploy:  ./scpme.sh <ip> [pass] [install]"
    exit 0
fi

echo
echo "=== uploading to $IP ==="
sshpass -p "$PASS" scp $SSH_OPTS "$NSL_ARCHIVE" root@"$IP":/tmp/

if [[ "$ACTION" != "install" ]]; then
    echo
    echo "→ archive copied to /tmp on $IP. To install:"
    echo "    ssh root@$IP 'cd /opt/influx && tar xzf /tmp/$(basename "$NSL_ARCHIVE") && bash netservices-lite/install.sh'"
    exit 0
fi

# --- 4. Install (ACTION=install) -------------------------------------------
echo
echo "=== installing netservices-lite on $IP ==="
sshpass -p "$PASS" ssh $SSH_OPTS root@"$IP" "
    set -e
    systemctl stop wifi-dashboard wifi-manager 2>/dev/null || true
    mkdir -p /opt/influx
    cd /opt/influx && tar xzf /tmp/$(basename "$NSL_ARCHIVE")
    chmod +x netservices-lite/install.sh
    bash netservices-lite/install.sh 2>&1 | tail -15
"

echo
echo "Done — netservices-lite ${NSL_VERSION} deployed to ${IP}."
