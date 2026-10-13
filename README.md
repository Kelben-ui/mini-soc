# Mini SOC Platform

A self-contained Security Operations Center (SOC) platform for detection, alerting, investigation, and response.

## Quick Start (EC2, systemd)

1. Clone/copy code to `/opt/mini-soc/` on EC2
2. Configure `/etc/mini-soc/.env` (from `.env.example`)
3. Run bootstrap: `bash /opt/mini-soc/deploy/install.sh`
4. Services: `systemctl status soc-backend soc-collector mini-soc-worker soc-agent mini-soc-ids`
5. Access via nginx (80/443/8443)

## Update
`bash /opt/mini-soc/deploy/update.sh` (git pull, deps, migrations, build, restart)

## Deployment notes
- **Detection loop:** production runs `mini-soc-worker.service` (`python -m detection.worker`). `deploy/systemd/soc-detection.service` is the legacy `detection/run.py` loop kept for reference — do not enable both (alerts would be processed twice).
- **nginx logging (Phase 1.2):** nginx must use the `soc` log format from `deploy/nginx/mini-soc.conf` (`access_log /var/log/nginx/access.log soc;`) — it appends `body=...` at the end of each line so the collector parser can URL-decode `uri`/`query`/`body` twice. Without it, web payloads arrive encoded and the WEB-* rules never fire.
- **Log agent (Phase 1.8):** `agents/log_agent/agent.py` tails `{nginx access.log, nginx error.log, auth.log, mini_soc_ids.json, kern.log}` and forwards raw lines to the collector. When the backend is down the collector answers `503` and the agent spools the lines to `AGENT_SPOOL_DIR` (`/var/lib/mini-soc/agent/spool`), replaying them once the collector is reachable.
- **Lab EC2 instance:** the live lab box runs the repo at `/home/ubuntu/mini-soc` (user `ubuntu`) with units `mini-soc-backend`, `mini-soc-collector`, `mini-soc-worker`, `mini-soc-ids` instead of `/opt/mini-soc` + `soc-*`. The repo is the single source of truth; the box is expected to be re-synced/rebuilt from `origin/main` (see recovery notes in this file below).
- **Security Group:** dashboard port (80) must be restricted to analyst IPs only (see Phase 0.3).

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
- Agent spool: `/var/lib/mini-soc/agent/spool/`
- Logs: journald (systemd units)
- IDS output: `/var/log/mini_soc_ids.json`

## Detection
Replay test (13 rules against SQLite or the configured DB):
`cd /opt/mini-soc && PYTHONPATH=/opt/mini-soc DATABASE_URL=sqlite:///./ci-replay.db .venv/bin/python detection/tests/replay_test.py` (expects "REPLAY TEST PASSED")

## Recovering the EC2 box from the repo (single source of truth)
If the lab box becomes unreachable ("kernel accepts TCP, sshd/nginx never answer"), it is likely wedged, not hacked. Recovery by an account with EC2 access (console → Instance state → Reboot); after boot, from the box:

```bash
cd /home/ubuntu/mini-soc
git fetch origin && git reset --hard origin/main                 # sync purged history
git reflog expire --expire=now --all && git gc --prune=now       # drop old .env.save blobs
cd frontend && npm ci && npm run build                           # rebuild dashboard (Tailwind v4)
sudo sed -i 's|/home/ubuntu/live_ids_ips.py|/home/ubuntu/mini-soc/infrastructure/fw-01/live_ids_ips.py|' /etc/systemd/system/mini-soc-ids.service
sudo systemctl daemon-reload && sudo systemctl restart mini-soc-ids
sudo rm -f /home/ubuntu/live_ids_ips.py.save* /home/ubuntu/live_ids_ips.py.bak*
sudo mkdir -p /home/ubuntu/infrastructure.bak
sudo mv /home/ubuntu/infrastructure/{collector,agents,docs,.pytest_cache} /home/ubuntu/infrastructure.bak/ 2>/dev/null   # stale duplicates; keep venv
systemctl status mini-soc-backend mini-soc-collector mini-soc-worker mini-soc-ids --no-pager | grep Active
```

Every referenced path and file lives in this repo at `origin/main`.
