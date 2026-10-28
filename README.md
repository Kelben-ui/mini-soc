# Mini SOC Platform

A self-contained Security Operations Center (SOC) platform for detection,
alerting, investigation, and response.

- Architecture: [docs/architecture.md](docs/architecture.md)
- Contracts: [docs/contracts.md](docs/contracts.md)
- Rules: [docs/rules.md](docs/rules.md)

## Quick Start (local lab)

### Option 1: Live end-to-end (recommended)

From the repo root on this host:

```bash
sudo bash scripts/live-e2e.sh            # start + verify everything
sudo bash scripts/live-e2e.sh --attack   # generate alerts
sudo bash scripts/live-e2e.sh --status   # report only
```

This brings up PostgreSQL, MariaDB, PHP-FPM, nginx (DVWA on `:80`, dashboard on
`:443`), nftables, rsyslog and the `soc-*`/IDS services, verifies them, and can
fire lab attack payloads. See [scripts/live-e2e.sh](scripts/live-e2e.sh) for
options.

### Option 2: Manual local development

Copy `.env.example` to `.env`, run the backend
(`uvicorn backend.app.main:app --reload`), and `cd frontend && npm run dev`.
Vite proxies `/api` to `127.0.0.1:8000`, mirroring nginx in production.

## Architecture

![Mini SOC system architecture](docs/images/architecture.png)

Editable source: [`docs/images/architecture.drawio`](docs/images/architecture.drawio);
regenerate the PNG with `python docs/images/render_architecture.py`. The
single-host layout (attackers → firewall → exposed services → collector/detection
→ PostgreSQL → dashboard) is described in full in
[docs/architecture.md](docs/architecture.md).

## Deviations from Original Design

| Original | Current | Reason |
|---|---|---|
| Docker-based deployment | Native systemd services (`deploy/systemd/` + `deploy/install.sh`/`deploy/update.sh`) | Simple host deployment; reproducible with systemd hardening |
| Suricata IDS | Custom lightweight IDS/IPS (`ids/`, `mini-soc-ids.service`) | Team's IDS/IPS with configurable thresholds and allow-lists; **detection-only**, with human-confirmed blocking via `soc-block` |
| Multi-VM distributed setup | Single host instance | Streamlined for lab/demo environment; all services on localhost |
| Dashboard on plain HTTP :80 | nginx TLS on :443 (self-signed by default) + :80 redirect | Protects credentials in transit |

## Key Paths

- Code: repo root (e.g. `/home/kelsey/mini-soc/`)
- Venv: `<repo>/.venv/`
- Config: `<repo>/.env` (repo root)
- Agent config: `<repo>/agents/agent.yaml`
- Evidence: `/var/lib/mini-soc/evidence/`
- Agent spool: `/var/lib/mini-soc/agent/spool/`
- Agent offsets: `/var/lib/mini-soc/agent/state.json`
- Detection checkpoint: `/var/lib/mini-soc/detection_checkpoint.json`
- Logs: journald (`journalctl -u soc-detection -f`)
- IDS output: `/var/log/mini_soc_ids.json`
- IDS config: `<repo>/ids/ids.yaml`
- Response allow-list: `<repo>/rules/allowlist.txt`
- Block helper: `/usr/local/sbin/soc-block` + `/etc/sudoers.d/mini-soc-soc-block`
- Host firewall: `/etc/nftables.conf`
- nginx site: `/etc/nginx/sites-available/mini-soc.conf`
- TLS cert/key: `/etc/ssl/mini-soc/mini-soc.{crt,key}`

## Detection

Replay test (13 rules against SQLite or the configured DB), from the repo root:

```bash
PYTHONPATH=. DATABASE_URL=sqlite:///./ci-replay.db .venv/bin/python detection/tests/replay_test.py
# expects "REPLAY TEST PASSED"
```

## Live end-to-end test (local lab)

`scripts/live-e2e.sh` brings up every component the demo path needs on this
host — PostgreSQL, MariaDB, PHP-FPM, nginx (DVWA on `:80`, dashboard on
`:443`), nftables, rsyslog and the five `soc-*`/IDS services — verifies each
one, and (with `--attack`) fires the lab attack payloads so the alerts and
events appear in the dashboard while you watch them:

```bash
sudo bash scripts/live-e2e.sh            # start + verify everything
sudo bash scripts/live-e2e.sh --attack   # ...then generate the alerts
sudo bash scripts/live-e2e.sh --status   # report only, change nothing
sudo bash scripts/live-e2e.sh --help     # all flags
```

The script is idempotent (it starts what is stopped and leaves healthy
services alone). Then open DVWA at `http://127.0.0.1/dvwa/login.php` (`admin` / `password`)
and the dashboard at `https://127.0.0.1/` (`admin` / the dashboard password —
override with `SOC_USER` / `SOC_PASS`). The pages that matter are
`/alerts` and `/events`.
