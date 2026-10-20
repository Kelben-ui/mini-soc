#!/bin/bash
# Create the local-lab attacker: a network namespace with a veth pair to the
# host, so attack traffic arrives on a real interface (not loopback).
#
# Why not just attack 127.0.0.1?  The lab firewall accepts all loopback traffic
# (`iif "lo" accept`), so anything sent to 127.0.0.1 bypasses nftables entirely
# and cannot exercise the drop / port-scan path.  A veth pair gives the host an
# external-looking source IP (10.99.0.2), which is what Kali -> EC2 looks like.
#
# Idempotent: safe to re-run.  Must be re-run after every WSL restart, because
# network namespaces do not persist across a reboot.
#
# Usage: sudo bash setup-attacker.sh
set -euo pipefail

NS=atk
HOST_IP=10.99.0.1
ATTACKER_IP=10.99.0.2
PREFIX=30
HOST_VETH=veth-soc-host
NS_VETH=veth-soc

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: must run as root (sudo bash $0)" >&2
    exit 1
fi

if ip netns list | grep -qw "$NS"; then
    echo "netns '$NS' already exists — recreating"
    ip netns del "$NS"
fi

# Clean up any half-created veth from a previous run.
ip link del "$HOST_VETH" 2>/dev/null || true

echo "Creating netns '$NS' with $ATTACKER_IP -> host $HOST_IP ..."
ip netns add "$NS"
ip link add "$HOST_VETH" type veth peer name "$NS_VETH"
ip link set "$NS_VETH" netns "$NS"

# Host side
ip addr add "$HOST_IP/$PREFIX" dev "$HOST_VETH"
ip link set "$HOST_VETH" up

# Attacker side
ip netns exec "$NS" ip link set lo up
ip netns exec "$NS" ip addr add "$ATTACKER_IP/$PREFIX" dev "$NS_VETH"
ip netns exec "$NS" ip link set "$NS_VETH" up
ip netns exec "$NS" ip route add default via "$HOST_IP"

# Make sure the attacker can resolve/install its own tools.
ip netns exec "$NS" bash -c 'command -v nmap >/dev/null || {
    echo "Installing nmap in the attacker namespace requires network access."; }'

echo
echo "Attacker ready."
echo "  namespace : $NS"
echo "  source IP : $ATTACKER_IP"
echo "  host IP   : $HOST_IP"
echo
echo "Run a command in it with:  ip netns exec $NS <cmd>"
