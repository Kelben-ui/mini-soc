#!/bin/bash
# LAB USE ONLY - triggers the Mini SOC "unusual outbound connection" detection.
#
# Unlike port-scan.sh / ssh-brute-force.sh (which run from Kali against the
# instance), this script runs ON the EC2 instance itself: the SOC_OUT nftables
# rule only logs connections the host initiates, and unusual_outbound
# (NET-OUTBOUND-001) fires on new outbound connections to a port outside the
# allow-list (53/80/443/123).
#
# Usage (on the instance):
#   ./outbound-conn.sh <dest_ip> [dest_port]
#
# Pick a dest_ip you control (or a reserved TEST-NET address) and a port that is
# NOT in IDS_OUTBOUND_ALLOW. The connection is expected to time out - that is
# fine, the firewall logs the SYN before the timeout.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGFILE="$SCRIPT_DIR/attack-log.txt"

DEST_IP="${1:-}"
DEST_PORT="${2:-4444}"

if [[ -z "$DEST_IP" ]]; then
    echo "usage: ./outbound-conn.sh <dest_ip> [dest_port]"
    echo "example: ./outbound-conn.sh 203.0.113.5 4444"
    exit 1
fi

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | outbound-conn | dest=$DEST_IP:$DEST_PORT | user=$(whoami)" >> "$LOGFILE"

# A bare TCP connect through bash's /dev/tcp. It either establishes or times
# out; either way the kernel emits a `ct state new` packet that nftables logs.
if timeout 3 bash -c "exec 3<>/dev/tcp/${DEST_IP}/${DEST_PORT}" 2>/dev/null; then
    echo "connected to ${DEST_IP}:${DEST_PORT}"
else
    echo "attempted outbound TCP ${DEST_IP}:${DEST_PORT} (no response - expected)"
fi

echo "Check the IDS log and the journal for a 'SOC_OUT:' line and an"
echo "unusual_outbound finding for ${DEST_IP}:${DEST_PORT}."
