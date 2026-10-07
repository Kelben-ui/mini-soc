#!/bin/bash
# LAB USE ONLY - target must match attack-sim/target.conf (your own EC2 instance)
# Usage: ./port-scan.sh <target_ip>

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

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | port-scan | target=$TARGET | user=$(whoami)" >> "$LOGFILE"

# -T4 keeps the scan fast enough to cross the >=20-ports-in-1-minute
# detection threshold; adjust if your connection to AWS is slow.
nmap -sS -T4 -p 1-1000 "$TARGET"
