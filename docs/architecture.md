# Mini SOC Platform — Architecture

This document describes the Mini SOC platform architecture and operational
model. It merges the original `docs/architecture` working draft; the previous
condensed summary is preserved under **Components** and **Deployment**.

## 1. Overview

The platform processes security information through the following lifecycle:

```
Detection → Alert → Investigation → Incident → Response → Resolution → Report
```

It consists of:

1. Log sources
2. Log agent
3. Central collector
4. Detection engine (custom-built IDS — see Section 2)
5. PostgreSQL database
6. Backend API
7. Dashboard

## 2. Deviations from the reference specification

This implementation differs from the original project specification
(Version 1.0, September 2026) in three ways, agreed with the supervisor:

| Area | Spec reference design | What we built instead | Reason |
|---|---|---|---|
| Intrusion detection | Suricata IDS on fw-01's inside interface, `eve.json` output | A custom Python IDS/IPS daemon (`ids/live_ids_ips.py`) — reads `journalctl` for auth/SSH events, detects Nmap/SSH brute-force patterns, and can block offending IPs | Team decision: a lightweight IDS/IPS with configurable thresholds and allow-lists is easier to run and understand in a one-VM lab, and satisfies the detection learning objectives without a Suricata dependency |
| Deployment / packaging | Docker Compose stack on soc-01, one-command startup | All components run as **systemd services directly on Ubuntu 24.04**, no containers | One-VM deployment; simpler ops and reproducible systemd hardening (NoNewPrivileges, ProtectSystem=strict, scoped ReadWritePaths) |
| Lab topology | 5 separate VMs (fw-01, web-01, srv-01, soc-01, atk-01) across an isolated two-segment network | **One AWS EC2 instance** hosts web target, SSH target, and the full SOC stack together. The attacker (Kali) is a local VM attacking over the internet | Avoids multi-VM resource requirements; EC2 gives a realistic internet-facing target |
| Code location | `/opt/mini-soc` | `/home/ubuntu/mini-soc` | Matches the live lab instance; the repo is the single source of truth for this path |

## 3. Data flow

```
Log Sources (auth.log, nginx access/error, kern.log/journal, IDS output)
        │   all local to the single EC2 instance — no network shipping
        ▼
   Log Agent (agents/log_agent/agent.py, tail + spool)
        │  tagged with log_type
        ▼
   Central Collector  (collector/main.py: parse, URL-decode, normalize)
        │  common event format (JSON), POST /api/ingest
        ▼
   PostgreSQL — events table
        │  new events (polled by detection/run.py)
        ▼
   Detection Engine (detection/engine/)  +  live_ids_ips.py (custom IDS/IPS)
        │  rules (YAML) + correlation + block actions
        ▼
   PostgreSQL — alerts table
        │
        ▼
   Backend API  (FastAPI, JWT auth)
        │  REST
        ▼
   Dashboard (React)
        │
        ▼
   SOC analyst (browser, from their own machine — see Section 4)
```

Notes:

- The untouched raw log line is always retained alongside the normalized event,
  per the common event format.
- Web target, SSH target, and the SOC stack are **one host**, so log shipping is
  local. The log agent tails the files and spools to disk while the backend is
  down (`AGENT_SPOOL_DIR`), replaying on recovery.
- `ids/live_ids_ips.py` detects (journalctl/auth-log parsing for Nmap and SSH
  brute-force patterns) and can enforce (host-level blocking). It writes JSON
  alerts to `IDS_OUTPUT` (`/var/log/mini_soc_ids.json`); the log agent forwards
  those lines to the collector, which normalizes them and stores them as events.
  It does **not** write to PostgreSQL directly.
- `detection/run.py` runs the detection engine in a loop with a checkpoint
  (`/var/lib/mini-soc/detection_checkpoint.json`) so alerts appear within a few
  seconds of a new event.

## 4. Deployment architecture (AWS EC2)

The canonical layout (created by `deploy/install.sh`):

| Thing | Value |
|---|---|
| Code | `/home/ubuntu/mini-soc` |
| Venv | `/home/ubuntu/mini-soc/.venv` |
| Config | `/etc/mini-soc/.env` (0640, `root:mini-soc`) |
| State | `/var/lib/mini-soc/{evidence,agent/spool}` |
| Logs | journald (`journalctl -u soc-backend -f`) |
| Database | PostgreSQL 16 on `localhost:5432` |
| Units | `soc-backend`, `soc-collector`, `soc-detection`, `soc-agent`, `mini-soc-ids` |

- **One EC2 instance** (Ubuntu 24.04) runs everything: Nginx + PHP-FPM + MariaDB
  + DVWA (web target), sshd with a test account (SSH target), and the full SOC
  stack as systemd services. See `docs/lab-setup.md` for instance details.
- **Security Group** is the perimeter control, replacing fw-01's nftables role
  for inbound filtering:
  - Inbound: TCP 22 and 80 are open so the attack can reach the box from the
    internet, matching the spec's "only 22 and 80 allowed" rule.
  - The dashboard/API nginx endpoint (443, plus 80 redirect) and the API itself
    (bound to `127.0.0.1:8000`) are restricted to analyst IPs only, not opened to
    the world. See `docs/testing/` and the Security Group notes in `README.md`.
  - Outbound: default allow, or tightened per `docs/testing/` findings.
- **No internal network segmentation** exists the way the original
  fw-01/lab-attack/lab-servers design had it — the Security Group is the only
  layer in that role. `live_ids_ips.py`'s host-level rules add a second layer.
- **The attacker (Kali) is a local VM on a laptop**, outside AWS, attacking the
  EC2 instance's **public IP** over the real internet. This means:
  - `src_ip` in alerts is the attacker's real public IP (dynamic, likely NATed),
    not a clean lab IP.
  - The false-positive demo with an "approved second IP" needs a substitute
    source (e.g. a phone hotspot or VPN) — record the choice in
    `docs/testing/` when rehearsed.
  - The box is reachable by real internet background scanning once 22/80 are
    open, which may add unrelated alerts during testing.
- **Time sync**: EC2 instances sync via the Amazon Time Sync Service by default —
  no custom NTP server is needed.
- **Snapshots**: use an AMI or EBS snapshot for "clean baseline" and "demo ready"
  states, replacing VM snapshots.
- **Cost control**: stop the instance when not actively testing or rehearsing.

## 4.1 AWS-specific safety rules (replaces physical-lab isolation rules)

- Only attack the IP of **your own EC2 instance**. Never scan or attack any other
  AWS resource, IP, or domain.
- This falls under AWS's self-testing allowance for EC2 instances you own: no
  sustained flooding/DoS-style traffic, no testing against anything outside your
  own account's resources.
- Keep the Security Group as tight as practical — only the ports you intend to
  expose should be open.
- Maintainers hold the EC2 key pair; credentials are kept out of the repo
  (`*.pem`, `.env`, and `.env.*` are git-ignored).
- Stop the instance outside of active test/demo sessions to limit both cost and
  exposure window.

## 5. Technology stack

| Layer | Technology | Notes |
|---|---|---|
| Host | AWS EC2, Ubuntu Server 24.04 LTS | Single instance — see Section 4 |
| Attacker | Kali Linux (local VM on laptop) | Attacks over the public internet |
| Web target | Nginx + PHP-FPM + MariaDB + DVWA | Custom log format includes request body |
| Intrusion detection/prevention | `ids/live_ids_ips.py` (custom Python daemon) | journalctl + host blocking; replaces Suricata — see Section 2 |
| Perimeter filtering | AWS Security Group | Replaces fw-01/nftables role — see Section 4 |
| Collector + detection | Python 3.11+ | Rules stored as YAML files |
| Database | PostgreSQL 16 | Schema managed with Alembic migrations |
| Backend API | FastAPI | JWT authentication |
| Frontend | React + Vite; Recharts | Polling for live alerts |
| Packaging | **Systemd services** (no Docker) | See Section 2 |
| TLS | Nginx on 443 (self-signed by default) | `deploy/nginx/mini-soc.conf` |
| Version control | Git + GitHub | Branches, pull requests, code review |

## 6. Components

| Component | Service | Purpose |
|---|---|---|
| Backend API | `soc-backend.service` | FastAPI REST API, auth, RBAC, incidents, alerts, evidence |
| Collector | `soc-collector.service` | Ingests raw logs, normalizes events (503 when the backend is down) |
| Detection | `soc-detection.service` | Loops the detection engine with a checkpoint; creates correlated alerts |
| Log Agent | `soc-agent.service` | Tails log files, forwards to the collector, spools during outages |
| IDS/IPS | `mini-soc-ids.service` | Custom IDS/IPS monitoring journal/network activity |
| Database | `postgresql.service` | PostgreSQL 16, localhost only |
| Web | `nginx.service` | Serves the built dashboard and proxies `/api` → `127.0.0.1:8000` |

## 7. Why these changes don't affect the rest of the design

- The **common event format** is unchanged, so the collector, detection engine,
  backend and frontend contracts all hold regardless of which IDS produces
  alerts or how services are deployed. See `docs/contracts.md`.
- The **database schema** is unchanged.
- The **alert/incident status lifecycle** is unchanged.
- Removing Docker only affects *how* services start (systemd units vs.
  `docker compose up`), not what they do or how they talk to each other.
