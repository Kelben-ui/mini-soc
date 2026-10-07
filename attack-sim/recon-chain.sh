#!/bin/bash
# LAB USE ONLY - target must match attack-sim/target.conf (your own EC2 instance)
# Usage: ./recon-chain.sh <target_ip>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF="$SCRIPT_DIR/target.conf"
TARGET="$1"
LOGFILE="$SCRIPT_DIR/attack-log.txt"

if [[ ! -f "$CONF" ]]; then
    echo "Missing $CONF — copy target.conf.example to target.conf and set ALLOWED_TARGET."
    exit 1
fi
source "$CONF"

if [[ -z "$TARGET" || "$TARGET" != "$ALLOWED_TARGET" ]]; then
    echo "Refusing to run: target must exactly match ALLOWED_TARGET in target.conf ($ALLOWED_TARGET)"
    exit 1
fi

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | recon-chain START | target=$TARGET | user=$(whoami)" >> "$LOGFILE"

echo "[1/4] Port scan..."
"$SCRIPT_DIR/port-scan.sh" "$TARGET"
sleep 5

echo "[2/4] SQL injection..."
"$SCRIPT_DIR/web-attacks.sh" "$TARGET" sqli
sleep 5

echo "[3/4] XSS..."
"$SCRIPT_DIR/web-attacks.sh" "$TARGET" xss
sleep 5

echo "[4/4] SSH brute force..."
"$SCRIPT_DIR/ssh-bruteforce.sh" "$TARGET" testuser "$SCRIPT_DIR/passlist.txt"

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | recon-chain END | target=$TARGET" >> "$LOGFILE"
