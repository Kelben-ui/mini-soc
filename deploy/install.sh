#!/bin/bash
# Mini SOC - EC2 systemd bootstrap (idempotent).
#
# One command to bring a fresh Ubuntu EC2 instance up:
#
#   sudo MINI_SOC_REPO_URL=https://github.com/Kelben-ui/mini-soc.git \
#        bash deploy/install.sh
#
# It installs packages, clones the repo, creates users/directories, builds the
# venv, provisions PostgreSQL 16, runs migrations, builds the frontend, renders
# the systemd units + nginx site, and starts every service.
#
# Layout:
#   code /home/ubuntu/mini-soc   venv /home/ubuntu/mini-soc/.venv
#   config /etc/mini-soc/.env (0640)   state /var/lib/mini-soc/{evidence,agent}
set -euo pipefail

# --- Configuration (override via environment) -------------------------------
APP_DIR="${MINI_SOC_APP_DIR:-/home/ubuntu/mini-soc}"
REPO_URL="${MINI_SOC_REPO_URL:-https://github.com/Kelben-ui/mini-soc.git}"
REPO_BRANCH="${MINI_SOC_BRANCH:-main}"
VENV_DIR="${VENV_DIR:-$APP_DIR/.venv}"
ETC_DIR="/etc/mini-soc"
VAR_DIR="${VAR_DIR:-/var/lib/mini-soc}"
EVIDENCE_DIR="${EVIDENCE_DIR:-$VAR_DIR/evidence}"
AGENT_DIR="${AGENT_DIR:-$VAR_DIR/agent}"
ENV_FILE="${ENV_FILE:-$ETC_DIR/.env}"
IDS_OUTPUT="${IDS_OUTPUT:-/var/log/mini_soc_ids.json}"
SOC_USER="${SOC_USER:-mini-soc}"
IDS_USER="${IDS_USER:-mini-soc-ids}"
TLS_DIR="${TLS_DIR:-/etc/ssl/mini-soc}"
DOMAIN="${DOMAIN:-_}"
TLS_CERT="${TLS_CERT:-$TLS_DIR/mini-soc.crt}"
TLS_KEY="${TLS_KEY:-$TLS_DIR/mini-soc.key}"

UNITS="soc-backend soc-collector soc-detection soc-agent mini-soc-ids"
LEGACY_UNITS="mini-soc-backend mini-soc-collector mini-soc-worker mini-soc-detection"

log() { echo "[install] $*"; }

if [ "$(id -u)" -ne 0 ]; then
  echo "[install] must run as root (use sudo)" >&2
  exit 1
fi

# --- Users ------------------------------------------------------------------
log "Creating service users"
id -u "$SOC_USER" >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin -d "$VAR_DIR" "$SOC_USER"
id -u "$IDS_USER" >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin -d "$VAR_DIR" "$IDS_USER"

# The login user that owns the checkout (usually 'ubuntu').
if id -u ubuntu >/dev/null 2>&1; then
  REPO_OWNER="ubuntu"
else
  REPO_OWNER="root"
fi

# --- Packages ---------------------------------------------------------------
log "Installing OS packages"
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  python3 python3-venv python3-pip git curl ca-certificates openssl nginx sudo rsyslog nftables

if ! command -v node >/dev/null 2>&1 || [ "$(node -v | sed 's/^v//; s/\..*//')" -lt 20 ]; then
  log "Installing Node.js 20 (NodeSource)"
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs
fi

# --- Checkout ---------------------------------------------------------------
if [ ! -d "$APP_DIR/.git" ]; then
  log "Cloning $REPO_URL -> $APP_DIR ($REPO_BRANCH)"
  mkdir -p "$(dirname "$APP_DIR")"
  git clone --branch "$REPO_BRANCH" "$REPO_URL" "$APP_DIR"
else
  log "Updating existing checkout"
  git -C "$APP_DIR" fetch --all --prune || true
  git -C "$APP_DIR" checkout "$REPO_BRANCH" 2>/dev/null || true
  git -C "$APP_DIR" pull --ff-only || true
fi

chown -R "$REPO_OWNER:$SOC_USER" "$APP_DIR"
chmod -R g+rX "$APP_DIR"
# nginx (www-data) needs to traverse into dist/.  Prefer a scoped ACL so we do
# not make the home directory world-executable; fall back to o+x only if the
# ACL tooling is unavailable.
if command -v setfacl >/dev/null 2>&1; then
  setfacl -m u:www-data:x "$(dirname "$APP_DIR")" "$APP_DIR" 2>/dev/null || true
else
  chmod o+x "$(dirname "$APP_DIR")" 2>/dev/null || true
  chmod o+x "$APP_DIR" 2>/dev/null || true
fi

# --- State directories ------------------------------------------------------
log "Creating state directories"
mkdir -p "$ETC_DIR" "$VAR_DIR" "$EVIDENCE_DIR" "$AGENT_DIR/spool"
chown -R "$SOC_USER:$SOC_USER" "$VAR_DIR"
chmod 750 "$VAR_DIR" "$EVIDENCE_DIR"

# The IDS writes this file; the log agent (group $SOC_USER) reads it.
touch "$IDS_OUTPUT"
chown "$IDS_USER:$SOC_USER" "$IDS_OUTPUT"
chmod 640 "$IDS_OUTPUT"

# --- System logs the agent tails -------------------------------------------
# rsyslog (not journald) produces /var/log/auth.log and /var/log/kern.log, and
# nginx writes /var/log/nginx/{access,error}.log.  The agent reads them through
# the `adm` group (see SupplementaryGroups= in soc-agent.service), so make sure
# rsyslog is running and every file exists before the service starts.
log "Ensuring rsyslog and log files"
systemctl enable --now rsyslog >/dev/null 2>&1 || true
systemctl restart rsyslog >/dev/null 2>&1 || true
mkdir -p /var/log/nginx
touch /var/log/auth.log /var/log/kern.log \
      /var/log/nginx/access.log /var/log/nginx/error.log
chgrp adm /var/log/auth.log /var/log/kern.log \
          /var/log/nginx/access.log /var/log/nginx/error.log 2>/dev/null || true
chmod 640 /var/log/auth.log /var/log/kern.log \
          /var/log/nginx/access.log /var/log/nginx/error.log 2>/dev/null || true

if [ ! -f "$ETC_DIR/ids.yaml" ] && [ -f "$APP_DIR/ids/ids.yaml" ]; then
  cp "$APP_DIR/ids/ids.yaml" "$ETC_DIR/ids.yaml"
fi
chmod 640 "$ETC_DIR/ids.yaml" 2>/dev/null || true
chown root:"$SOC_USER" "$ETC_DIR/ids.yaml" 2>/dev/null || true

# --- Log agent config -------------------------------------------------------
# /etc/mini-soc/agent.yaml drives the agent (collector URL, files, batching,
# buffer dir - task 3.1).  Only create it on first install so operator edits
# survive re-runs.
if [ ! -f "$ETC_DIR/agent.yaml" ] && [ -f "$APP_DIR/agents/agent.example.yaml" ]; then
  log "Installing $ETC_DIR/agent.yaml"
  cp "$APP_DIR/agents/agent.example.yaml" "$ETC_DIR/agent.yaml"
fi
chmod 640 "$ETC_DIR/agent.yaml" 2>/dev/null || true
chown root:"$SOC_USER" "$ETC_DIR/agent.yaml" 2>/dev/null || true

# --- Config file ------------------------------------------------------------
if [ ! -f "$ENV_FILE" ]; then
  log "Creating $ENV_FILE and generating secrets"
  cp "$APP_DIR/.env.example" "$ENV_FILE"

  JWT_SECRET="$(openssl rand -hex 32)"
  INGEST_KEY="$(openssl rand -hex 24)"
  DB_PASSWORD="$(openssl rand -hex 24)"

  sed -i "s|CHANGE_ME_JWT_SECRET|$JWT_SECRET|" "$ENV_FILE"
  sed -i "s|CHANGE_ME_INGEST_KEY|$INGEST_KEY|" "$ENV_FILE"
  sed -i "s|postgresql://mini_soc:CHANGE_ME@|postgresql://mini_soc:$DB_PASSWORD@|" "$ENV_FILE"
  sed -i "s|^APP_DIR=.*|APP_DIR=$APP_DIR|" "$ENV_FILE"
  sed -i "s|^RULES_DIR=.*|RULES_DIR=$APP_DIR/rules|" "$ENV_FILE"
  sed -i "s|^DETECTION_RULES_DIR=.*|DETECTION_RULES_DIR=$APP_DIR/rules|" "$ENV_FILE"
else
  log "Keeping existing $ENV_FILE"
fi
chmod 640 "$ENV_FILE"
chown root:"$SOC_USER" "$ENV_FILE"

# --- Python venv ------------------------------------------------------------
log "Setting up venv at $VENV_DIR"
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
chown -R "$REPO_OWNER:$SOC_USER" "$VENV_DIR"
chmod -R g+rX "$VENV_DIR"

# --- Response-action helper + allow-list (task 4.7) -------------------------
# The allow-list is rendered from ids.yaml so the helper and the backend
# enforce exactly the same set the IDS suppresses (defence in depth).
log "Installing response-action helper and allow-list"
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

# --- PostgreSQL 16 + migrations --------------------------------------------
log "Provisioning PostgreSQL"
ENV_FILE="$ENV_FILE" VENV_DIR="$VENV_DIR" bash "$APP_DIR/deploy/postgres.sh"

log "Running alembic migrations"
( cd "$APP_DIR/backend" && ENV_FILE="$ENV_FILE" "$VENV_DIR/bin/python" -m alembic upgrade head )

# --- Frontend ---------------------------------------------------------------
log "Building frontend"
( cd "$APP_DIR/frontend" && npm ci && npm run build )
chmod -R o+rX "$APP_DIR/frontend/dist" 2>/dev/null || true

# --- systemd units ----------------------------------------------------------
log "Rendering systemd units"
for unit in $UNITS; do
  sed -e "s|@APP_DIR@|$APP_DIR|g" \
      -e "s|@VENV_DIR@|$VENV_DIR|g" \
      -e "s|@ENV_FILE@|$ENV_FILE|g" \
      -e "s|@SOC_USER@|$SOC_USER|g" \
      -e "s|@IDS_USER@|$IDS_USER|g" \
      "$APP_DIR/deploy/systemd/${unit}.service" > "/etc/systemd/system/${unit}.service"
done

for unit in $LEGACY_UNITS; do
  systemctl disable --now "$unit" >/dev/null 2>&1 || true
  rm -f "/etc/systemd/system/${unit}.service"
done

systemctl daemon-reload
systemctl enable $UNITS >/dev/null 2>&1 || true

# --- nginx + TLS ------------------------------------------------------------
log "Configuring nginx"
mkdir -p "$TLS_DIR"
if [ ! -f "$TLS_CERT" ] || [ ! -f "$TLS_KEY" ]; then
  log "Generating self-signed certificate for CN=$DOMAIN"
  openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
    -keyout "$TLS_KEY" -out "$TLS_CERT" \
    -subj "/CN=${DOMAIN}" \
    -addext "subjectAltName=DNS:${DOMAIN},IP:127.0.0.1" >/dev/null 2>&1
  chmod 600 "$TLS_KEY"
fi

sed -e "s|@APP_DIR@|$APP_DIR|g" \
    -e "s|@DOMAIN@|$DOMAIN|g" \
    -e "s|@TLS_CERT@|$TLS_CERT|g" \
    -e "s|@TLS_KEY@|$TLS_KEY|g" \
    "$APP_DIR/deploy/nginx/mini-soc.conf" > /etc/nginx/sites-available/mini-soc.conf
ln -sf /etc/nginx/sites-available/mini-soc.conf /etc/nginx/sites-enabled/mini-soc.conf
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl enable --now nginx >/dev/null 2>&1 || true
systemctl reload nginx

# --- Host firewall (task 4.1/4.4) -------------------------------------------
# nftables logs input drops (SOC_DROP:) and new outbound connections (SOC_OUT:)
# for the IDS.  Validate the ruleset before applying it so a typo can never
# lock the host out.
log "Installing nftables firewall"
install -m 0644 "$APP_DIR/deploy/nftables/mini-soc.conf" /etc/nftables.conf
if nft -c -f /etc/nftables.conf; then
  nft -f /etc/nftables.conf
  systemctl enable --now nftables >/dev/null 2>&1 || true
  systemctl restart nftables >/dev/null 2>&1 || true
else
  echo "[install] WARNING: /etc/nftables.conf failed validation; firewall not applied" >&2
fi

# --- Start services ---------------------------------------------------------
log "Starting services"
systemctl restart $UNITS

log "Install complete."
systemctl --no-pager --lines=0 status $UNITS || true
echo
echo "Dashboard: https://<host>/   (self-signed cert if DOMAIN=_ was used)"
echo "Logs:      journalctl -u soc-backend -f"
