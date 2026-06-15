#!/usr/bin/env bash
#
# Опаковане на netservices-lite (Wi-Fi only вариант) в deploy архив.
#
# По-малък брат на netservices/scripts/pack.sh — няма modules/, няма xoraya,
# само dashboard/, services/, systemd/ + install.sh.
#
# Употреба (от корена на netservices-lite/):
#   ./scripts/pack.sh                 # → dist/netservices-lite-<ver>-deploy.tar.gz
#   ./scripts/pack.sh deploy
#   ./scripts/pack.sh source
#   ./scripts/pack.sh all
#
# Опции (env vars):
#   DIST_DIR=/tmp/out    # къде да слага архивите (default: ./dist)
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${DIST_DIR:-$ROOT_DIR/dist}"
MODE="${1:-deploy}"
NAME="netservices-lite"

# --- Прочитане на DASHBOARD_VERSION от dashboard/app.py --------------------
APP_PY="$ROOT_DIR/dashboard/app.py"
[[ -f "$APP_PY" ]] || { echo "missing $APP_PY"; exit 1; }
VERSION=$(awk -F'"' '/^DASHBOARD_VERSION = "/ {print $2; exit}' "$APP_PY")
[[ -n "$VERSION" ]] || { echo "could not parse DASHBOARD_VERSION from $APP_PY"; exit 1; }

mkdir -p "$DIST_DIR"

COMMON_EXCLUDES=(
    --exclude='**/__pycache__'
    --exclude='**/*.pyc'
    --exclude='**/.svn'
    --exclude='**/.git'
    --exclude='**/.DS_Store'
    --exclude='dist'
    --exclude='.claude'
    --exclude='.codex'
)

INCLUDE_BASE=(
    dashboard
    services
    systemd
    install.sh
)

build_deploy() {
    local out="$DIST_DIR/${NAME}-${VERSION}-deploy.tar.gz"
    local DEPLOY_EXCLUDES=(
        "${COMMON_EXCLUDES[@]}"
        --exclude='scripts/pack.sh'
    )
    echo "→ creating $out"
    # Архивът съдържа top-level папка `netservices-lite/` за да match-ва
    # install.sh-а, който очаква DEST=/opt/influx/netservices-lite/.
    tar czf "$out" \
        -C "$(dirname "$ROOT_DIR")" \
        "${DEPLOY_EXCLUDES[@]}" \
        --transform "s|^$(basename "$ROOT_DIR")|netservices-lite|" \
        $(for i in "${INCLUDE_BASE[@]}"; do echo "$(basename "$ROOT_DIR")/$i"; done)
    _summary "$out"
}

build_source() {
    local out="$DIST_DIR/${NAME}-${VERSION}-source.tar.gz"
    echo "→ creating $out"
    tar czf "$out" \
        -C "$(dirname "$ROOT_DIR")" \
        "${COMMON_EXCLUDES[@]}" \
        --transform "s|^$(basename "$ROOT_DIR")|netservices-lite|" \
        "$(basename "$ROOT_DIR")"
    _summary "$out"
}

_summary() {
    local f="$1"
    local size=$(du -h "$f" | awk '{print $1}')
    local sha=$(sha256sum "$f" | awk '{print $1}')
    echo "   path:   $f"
    echo "   size:   $size"
    echo "   sha256: $sha"
    echo "$sha  $(basename "$f")" > "$f.sha256"
}

case "$MODE" in
    deploy) build_deploy ;;
    source) build_source ;;
    all)    build_deploy; echo; build_source ;;
    *)      echo "Непознат режим: $MODE (валидни: deploy, source, all)"; exit 2 ;;
esac

echo
echo "Done — $NAME $VERSION → $DIST_DIR"
