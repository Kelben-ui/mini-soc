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

log "Restarting services"
systemctl restart $UNITS

log "Update complete."
systemctl --no-pager --lines=0 status $UNITS || true
