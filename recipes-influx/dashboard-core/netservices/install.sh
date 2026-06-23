#!/bin/sh
# Install netservices (Cython compiled, arm64)
set -e
DEST=/opt/influx/netservices
echo "Installing netservices to $DEST"

systemctl stop wifi-dashboard wifi-manager 2>/dev/null || true
mkdir -p "$DEST/bin" "$DEST/lib" "$DEST/scripts" "$DEST/ssl" "$DEST/licensing"
cp -rf lib/. "$DEST/lib/"
cp -f bin/* "$DEST/bin/"
chmod +x "$DEST/bin/"*

cp -f systemd/*.service /etc/systemd/system/
[ -f systemd/20-wireless-wlan0.network ] && cp -f systemd/20-wireless-wlan0.network /etc/systemd/network/
cp -f scripts/*.sh "$DEST/scripts/" 2>/dev/null || true
[ -d ssl ] && [ -z "$(ls -A $DEST/ssl 2>/dev/null)" ] && cp -rf ssl/. "$DEST/ssl/" || true
[ -d licensing ] && cp -rf licensing/. "$DEST/licensing/" || true

systemctl daemon-reload
systemctl enable wifi-manager wifi-dashboard
systemctl restart wifi-manager wifi-dashboard
echo "Done."
