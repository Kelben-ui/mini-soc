# Mini SOC Platform

A self-contained Security Operations Center (SOC) platform for detection, alerting, investigation, and response.

## Quick Start (EC2, systemd)

1. Clone/copy code to `/opt/mini-soc/` on EC2
2. Configure `/etc/mini-soc/.env` (from `.env.example`)
3. Run bootstrap: `bash /opt/mini-soc/deploy/install.sh`
4. Services: `systemctl status soc-backend soc-collector soc-detection soc-agent mini-soc-ids`
5. Access via nginx (80/443/8443)

## Update
`bash /opt/mini-soc/deploy/update.sh` (git pull, deps, migrations, build, restart)

## Architecture
See [docs/architecture.md](docs/architecture.md).

## Deviations from Original Design

| Original | Current (EC2/systemd) | Reason |
|---|---|---|
| Docker-based deployment | Native systemd services (deploy/systemd/ + install.sh/update.sh) | One-VM EC2 deployment; simpler ops, reproducible with systemd hardening |
| Suricata IDS | Custom lightweight IDS (`ids/`, `mini-soc-ids.service`) | Team's IDS/IPS with configurable thresholds, allow-lists, IPS block helper |
| Multi-VM distributed setup | Single EC2 instance | Streamlined for lab/demo environment; all services on localhost |

## Key Paths
- Code: `/opt/mini-soc/`
- Venv: `/opt/mini-soc/.venv/`
- Config: `/etc/mini-soc/.env` (0640)
- Evidence: `/var/lib/mini-soc/evidence/`
- Logs: journald (systemd units)
- IDS output: `/var/log/mini_soc_ids.json`

## Detection
Replay test: `cd /opt/mini-soc && PYTHONPATH=/opt/mini-soc .venv/bin/python detection/tests/replay_test.py` (expects "REPLAY TEST PASSED")
