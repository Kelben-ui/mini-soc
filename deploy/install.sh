#!/bin/bash
set -euo pipefail

# Mini SOC - EC2 systemd install (idempotent)

# Variables (override via env)
APP_DIR="/opt/mini-soc"
VENV_DIR="/opt/mini-soc/.venv"
ETC_DIR="/etc/mini-soc"
VAR_DIR="/var/lib/mini-soc"
EVIDENCE_DIR="/var/lib/mini-soc/evidence"
AGENT_DIR="/var/lib/mini-soc/agent"
ENV_FILE="/etc/mini-soc/.env"
IDS_DIR="/opt/mini-soc/ids"

log() { echo "[install] $*"; }

log "Creating users and directories..."
id -u mini-soc >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin -d "$APP_DIR" mini-soc
id -u mini-soc-ids >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin -d "$IDS_DIR" mini-soc-ids

mkdir -p "$APP_DIR" "$VENV_DIR" "$ETC_DIR" "$VAR_DIR" "$EVIDENCE_DIR" "$AGENT_DIR"
chown mini-soc:mini-soc "$APP_DIR" "$VENV_DIR" "$VAR_DIR" "$EVIDENCE_DIR" "$AGENT_DIR"
chmod 755 "$APP_DIR" "$VAR_DIR"

if [ ! -f "$ENV_FILE" ]; then
  log "Creating default env at $ENV_FILE"
  cp .env.example "$ENV_FILE" 2>/dev/null || true
fi
chmod 640 "$ENV_FILE"
chown root:mini-soc "$ENV_FILE" 2>/dev/null || true

log "Setting up Python venv..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip >/dev/null

if [ -f "$APP_DIR/requirements.txt" ]; then
  "$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"
fi

log "Installing systemd units..."
cp "$APP_DIR/deploy/systemd/soc-backend.service" /etc/systemd/system/
cp "$APP_DIR/deploy/systemd/soc-collector.service" /etc/systemd/system/
cp "$APP_DIR/deploy/systemd/mini-soc-worker.service" /etc/systemd/system/
cp "$APP_DIR/deploy/systemd/soc-agent.service" /etc/systemd/system/
cp "$APP_DIR/deploy/systemd/mini-soc-ids.service" /etc/systemd/system/

systemctl daemon-reload
systemctl enable --now soc-backend.service soc-collector.service mini-soc-worker.service soc-agent.service mini-soc-ids.service 2>/dev/null || true

log "Install complete (idempotent)."
echo "Services status: systemctl status soc-backend soc-collector mini-soc-worker soc-agent mini-soc-ids"
