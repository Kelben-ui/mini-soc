# Attack Simulation Scripts

This directory contains scripts to simulate common attack patterns against
the lab environment for testing the Mini SOC detection capabilities.

**Only run these against your own lab instance.**

## Overview

The platform runs as a single host instance. All services (DVWA, dashboard,
collector, detection, etc.) run on the same host.

## Prerequisites

- Lab environment running (see main README / `scripts/live-e2e.sh`)
- Target host accessible (default: `127.0.0.1`)
- Proper authorization to run these tests

## Setup

1. Copy the target config and set it to your lab instance's IP:

   ```bash
   cp target.conf.example target.conf
   # edit target.conf: ALLOWED_TARGET="<your lab IP>"
   ```

2. Make scripts executable:

   ```bash
   chmod +x *.sh
   ```

## Available Scripts

| Script | Attack Type | Rule Triggered | Usage |
|--------|-------------|----------------|-------|
| `port-scan.sh` | Network reconnaissance | NET-PORTSCAN-001 | `./port-scan.sh <TARGET_IP>` |
| `ssh-brute-force.sh` | SSH authentication brute force | SSH-BF-001, SSH-SUCCESS-001 | `./ssh-brute-force.sh <TARGET_IP> <user> <passlist>` |
| `sqli-xss.sh` | SQL injection & XSS | WEB-SQLI-001, WEB-XSS-001 | `./sqli-xss.sh <TARGET_IP> [sqli\|xss\|all]` |
| `web-command-injection.sh` | Command injection | WEB-CMD-001 | `./web-command-injection.sh <TARGET_IP>` |
| `web-traversal-lfi.sh` | Directory traversal/LFI | WEB-LFI-001 | `./web-traversal-lfi.sh <TARGET_IP>` |
| `web-brute-force.sh` | Web login brute force (DVWA) | WEB-BF-001 | `./web-brute-force.sh <TARGET_IP>` |
| `scanner-ua.sh` | Scanner user agent | WEB-SCAN-001 | `./scanner-ua.sh <TARGET_IP>` |
| `http-flood.sh` | HTTP flood | WEB-FLOOD-001 | `./http-flood.sh <TARGET_IP>` |
| `dns-tunnel-sim.sh` | DNS anomalies | DNS-ANOMALY-001 | `./dns-tunnel-sim.sh <TARGET_IP>` |
| `unusual-outbound-sim.sh` | Unusual outbound | NET-OUTBOUND-001 | `./unusual-outbound-sim.sh <TARGET_IP>` |
| `recon-chain.sh` | Multi-stage attack chain | Multiple rules | `./recon-chain.sh <TARGET_IP>` |

## Example Usage

```bash
./port-scan.sh 127.0.0.1
./ssh-brute-force.sh 127.0.0.1 testuser passlist.txt
./sqli-xss.sh 127.0.0.1 all
./web-command-injection.sh 127.0.0.1
./web-traversal-lfi.sh 127.0.0.1
./web-brute-force.sh 127.0.0.1
./scanner-ua.sh 127.0.0.1
./recon-chain.sh 127.0.0.1
```

## Important Notes

- All scripts include safety checks to prevent running against unauthorized targets
- Use `target.conf` to configure allowed targets
- These scripts are for educational/testing purposes only in isolated lab environments
- When running on the same host, you may need to use the appropriate namespace/networking setup depending on your lab configuration
