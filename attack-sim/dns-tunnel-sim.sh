#!/bin/bash
# LAB USE ONLY - triggers the Mini SOC "unusual DNS activity" detection.
#
# Like outbound-conn.sh this runs ON the EC2 instance: the IDS sniffs DNS
# queries leaving the host (AF_PACKET on UDP/53) and raises DNS-ANOMALY-001
# (task 4.5). The signature fires when a query label is longer than
# IDS_DNS_MAX_LABEL (default 50), the classic shape of DNS tunnelling.
#
# Usage (on the instance):
#   ./dns-tunnel-sim.sh [count]
#
# The lookups are expected to fail (the domain does not exist) - that is fine,
# the query still leaves the host.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGFILE="$SCRIPT_DIR/attack-log.txt"

COUNT="${1:-5}"

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | dns-tunnel-sim | count=$COUNT | user=$(whoami)" >> "$LOGFILE"

# 60 'a' characters - longer than the default IDS_DNS_MAX_LABEL of 50 - in
# front of a label that will never resolve.
LABEL="$(printf 'a%.0s' $(seq 1 60))"
HOSTNAME="${LABEL}.tunnel.example.com"

for _ in $(seq 1 "$COUNT"); do
    # Prefer dig, fall back to nslookup, then to a python resolver so the
    # script works on a bare instance with none of the DNS tools installed.
    if command -v dig >/dev/null 2>&1; then
        dig +short +timeout=1 +tries=1 "$HOSTNAME" >/dev/null 2>&1 || true
    elif command -v nslookup >/dev/null 2>&1; then
        nslookup "$HOSTNAME" >/dev/null 2>&1 || true
    else
        python3 - "$HOSTNAME" <<'PY' || true
import socket
import sys

try:
    socket.getaddrinfo(sys.argv[1], 80)
except OSError:
    pass
PY
    fi

    sleep 1
done

echo "Sent ${COUNT} lookups for ${HOSTNAME}."
echo "Check the IDS log and the journal for a 'dns_query' event and an"
echo "unusual_dns finding."
