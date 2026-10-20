#!/bin/bash
# LAB USE ONLY - target must match attack-sim/target.conf (your own EC2 instance)
# Usage: ./scanner-ua.sh <target_ip>
#
# Sends a handful of requests carrying the User-Agent strings real offensive
# scanners use, to fire WEB-SCAN-001 (scanner user-agent, MEDIUM). The rule
# only needs the UA to be present, so this is the smallest trigger for it.

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

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | scanner-ua | target=$TARGET | user=$(whoami)" >> "$LOGFILE"

# Each UA carries one of the tokens WEB-SCAN-001 matches: sqlmap, nikto,
# nmap, gobuster. Detection is case-insensitive; use the real strings.
for ua in \
    "sqlmap/1.8#stable (http://sqlmap.org)" \
    "Nikto/2.5.0" \
    "Nmap Scripting Engine; https://nmap.org/book/nse.html" \
    "gobuster/3.6"
do
    echo "  User-Agent: $ua"
    curl -s -A "$ua" "http://$TARGET/" -o /dev/null
    sleep 1
done
