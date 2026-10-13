#!/bin/bash
set -euo pipefail

APP_DIR="/opt/mini-soc"
VENV_DIR="/opt/mini-soc/.venv"

log() { echo "[update] $*"; }

cd "$APP_DIR"

# Pull latest (if git repo)
if [ -d .git ]; then
  log "git pull"
  git pull --ff-only || true
fi

log "Updating venv deps..."
"$VENV_DIR/bin/pip" install -q --upgrade pip
if [ -f requirements.txt ]; then
  "$VENV_DIR/bin/pip" install -q -r requirements.txt
fi

# Alembic migrations if migrations dir exists
if [ -d backend/migrations ]; then
  log "Running alembic upgrade head"
  (cd backend && "$VENV_DIR/bin/python" -m alembic upgrade head) || true
fi

# Frontend build if package.json exists
if [ -f frontend/package.json ]; then
  log "Building frontend"
  (cd frontend && npm ci && npm run build) || true
fi

log "Restarting services..."
systemctl restart soc-backend soc-collector mini-soc-worker soc-agent mini-soc-ids 2>/dev/null || true

log "Update complete."
systemctl status --no-pager soc-backend soc-collector mini-soc-worker 2>&1 | tail -5
