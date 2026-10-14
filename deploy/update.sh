#!/bin/bash
# Mini SOC - update an existing EC2 deployment.
#
# Pulls the latest code, refreshes dependencies + migrations + frontend build,
# re-renders the systemd units and restarts every service.  Run as root.
set -euo pipefail

APP_DIR="${MINI_SOC_APP_DIR:-/home/ubuntu/mini-soc}"
VENV_DIR="${VENV_DIR:-$APP_DIR/.venv}"
ETC_DIR="${ETC_DIR:-/etc/mini-soc}"
ENV_FILE="${ENV_FILE:-$ETC_DIR/.env}"
SOC_USER="${SOC_USER:-mini-soc}"
IDS_USER="${IDS_USER:-mini-soc-ids}"
UNITS="soc-backend soc-collector soc-detection soc-agent mini-soc-ids"

log() { echo "[update] $*"; }

if [ "$(id -u)" -ne 0 ]; then
  echo "[update] must run as root (use sudo)" >&2
  exit 1
fi

log "Pulling latest in $APP_DIR"
branch="$(git -C "$APP_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"
git -C "$APP_DIR" fetch --all --prune || true
git -C "$APP_DIR" reset --hard "origin/$branch" || true

log "Updating venv dependencies"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

log "Running alembic migrations"
( cd "$APP_DIR/backend" && ENV_FILE="$ENV_FILE" "$VENV_DIR/bin/python" -m alembic upgrade head )

log "Building frontend"
( cd "$APP_DIR/frontend" && npm ci && npm run build )
chmod -R o+rX "$APP_DIR/frontend/dist" 2>/dev/null || true

log "Re-rendering systemd units"
for unit in $UNITS; do
  sed -e "s|@APP_DIR@|$APP_DIR|g" \
      -e "s|@VENV_DIR@|$VENV_DIR|g" \
      -e "s|@ENV_FILE@|$ENV_FILE|g" \
      -e "s|@SOC_USER@|$SOC_USER|g" \
      -e "s|@IDS_USER@|$IDS_USER|g" \
      "$APP_DIR/deploy/systemd/${unit}.service" > "/etc/systemd/system/${unit}.service"
done
systemctl daemon-reload

# --- Response-action helper + firewall (task 4.4/4.7) -----------------------
log "Refreshing response-action helper and allow-list"
ALLOWLIST_FILE="${ALLOWLIST_FILE:-$ETC_DIR/allowlist.txt}"
"$VENV_DIR/bin/python" - "$ETC_DIR/ids.yaml" "$ALLOWLIST_FILE" <<'PY'
import sys

import yaml

config_path, allowlist_path = sys.argv[1], sys.argv[2]

with open(config_path, encoding="utf-8") as handle:
    config = yaml.safe_load(handle) or {}

allow = config.get("allow_list") or {}
ips = []

for key in ("analyst_ips", "approved_scanner_ips"):
    for ip in allow.get(key) or []:
        ip = str(ip).strip()
        if ip and ip not in ips:
            ips.append(ip)

with open(allowlist_path, "w", encoding="utf-8") as handle:
    for ip in ips:
        handle.write(f"{ip}\n")
PY
chmod 640 "$ALLOWLIST_FILE" 2>/dev/null || true
chown root:"$SOC_USER" "$ALLOWLIST_FILE" 2>/dev/null || true

install -m 0755 "$APP_DIR/deploy/soc-block" /usr/local/sbin/soc-block
sed -e "s|@SOC_USER@|$SOC_USER|g" \
    "$APP_DIR/deploy/sudoers/mini-soc-soc-block" \
    > /etc/sudoers.d/mini-soc-soc-block
chmod 0440 /etc/sudoers.d/mini-soc-soc-block
chown root:root /etc/sudoers.d/mini-soc-soc-block
if command -v visudo >/dev/null 2>&1; then
  visudo -cf /etc/sudoers.d/mini-soc-soc-block >/dev/null
fi

log "Refreshing nftables firewall"
install -m 0644 "$APP_DIR/deploy/nftables/mini-soc.conf" /etc/nftables.conf
if nft -c -f /etc/nftables.conf; then
  systemctl restart nftables >/dev/null 2>&1 || nft -f /etc/nftables.conf
else
  echo "[update] WARNING: /etc/nftables.conf failed validation; firewall not applied" >&2
fi

log "Restarting services"
systemctl restart $UNITS

log "Update complete."
systemctl --no-pager --lines=0 status $UNITS || true
