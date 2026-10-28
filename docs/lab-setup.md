# Lab setup — building the Mini SOC lab environment

This guide describes how to build and configure the Mini SOC lab environment on a single host.

> Host-config snapshots may live in `infrastructure/` for review; the
> authoritative installer is `deploy/install.sh`.

## Prerequisites

- Ubuntu/Debian-based host with sudo access
- Git, curl, ca-certificates
- Sufficient resources (recommended: 4+ GB RAM, 20+ GB disk)

## Quick setup

1. Clone the repo:
```bash
git clone https://github.com/Kelben-ui/mini-soc.git ~/mini-soc
cd ~/mini-soc
```

2. Run the installer (or use the live-e2e script):
```bash
sudo bash deploy/install.sh
# or
sudo bash scripts/live-e2e.sh
```

The live-e2e script is the recommended way for local development/testing as it
orchestrates all components (PostgreSQL, MariaDB, PHP-FPM, nginx, nftables,
rsyslog, soc-* services, IDS).

## Manual configuration (if needed)

See `deploy/README.md` for details on what the installer does. For DVWA setup,
see the live-e2e script or follow standard DVWA installation on the host.

## Services

After setup, manage services with systemd:
```bash
systemctl status soc-backend soc-collector soc-detection soc-agent mini-soc-ids
```

## Access

- Dashboard: https://127.0.0.1/ (self-signed cert by default)
- DVWA: http://127.0.0.1/dvwa/
