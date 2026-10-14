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

![Mini SOC architecture](images/architecture.png)

*Editable source: `docs/images/architecture.drawio`; regenerate the PNG with
`python docs/images/render_architecture.py`.*

## 2. Deviations from the reference specification

This implementation differs from the original project specification
(Version 1.0, September 2026) in three ways, agreed with the supervisor:

| Area | Spec reference design | What we built instead | Reason |
|---|---|---|---|
| Intrusion detection | Suricata IDS on fw-01's inside interface, `eve.json` output | A custom Python IDS/IPS daemon (`ids/live_ids_ips.py`) — reads the journal for firewall/SSH events plus a raw DNS sniffer, applies configurable signatures, and writes Suricata-style JSON | Team decision: a lightweight IDS/IPS with configurable thresholds and allow-lists is easier to run and understand in a one-VM lab, and satisfies the detection learning objectives without a Suricata dependency |
| Intrusion prevention | Suricata inline drop | **Human-confirmed host blocking**: the analyst confirms a `block IP` action in the dashboard and the backend runs the small `soc-block` helper through a sudoers entry to add the address to the nftables `blocklist` set. Detection never blocks on its own | Keeps a person in the loop for every block (contracts §9.5) and constrains the only privileged action to one audited script |
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
- `ids/live_ids_ips.py` is **detection-only**. It parses firewall log lines
  (`SOC_DROP:`/`SOC_OUT:` from nftables via the journal) and SSH auth failures,
  plus raw DNS queries off the wire, and writes JSON alerts to `IDS_OUTPUT`
  (`/var/log/mini_soc_ids.json`); the log agent forwards those lines to the
  collector, which normalizes them and stores them as events. It does **not**
  write to PostgreSQL directly and never blocks on its own — see Section 3.2.
- `detection/run.py` runs the detection engine in a loop with a checkpoint
  (`/var/lib/mini-soc/detection_checkpoint.json`) so alerts appear within a few
  seconds of a new event.

### 3.1 Log agent (Phase 3 rewrite, spec §4.1)

`agents/log_agent/` is config-driven: everything the agent does is read from
`/etc/mini-soc/agent.yaml` (rendered from `agents/agent.example.yaml` by
`install.sh`) - collector URL, API key, host, heartbeat, batch sizes, buffer
dir and the source list.  Behaviour:

- **Offsets (3.2)** — `(path, inode)` byte offsets persist in
  `/var/lib/mini-soc/agent/state.json` (atomic writes); a restart resumes
  exactly where it stopped, so nothing is lost or duplicated.
- **Rotation/truncation (3.3)** — on an inode change the old file is drained
  to EOF before the new file is opened at byte 0; a same-inode truncation is
  re-read from 0.
- **Batching (3.4)** — lines are grouped per source and **one** POST
  `{host, log_type, lines: [...]}` is sent per batch (N lines or T seconds).
  The collector accepts both the batched shape and the legacy single-line one,
  and verifies the agent's `X-API-Key` header against `INGEST_API_KEY`.
- **Spool (3.5)** — failed batches are appended to `agent/spool/batches.jsonl`
  and replayed FIFO with exponential backoff (1 s → 60 s), so a 2-minute
  collector outage loses nothing.
- **Sources (3.6)** — file sources (nginx access/error, auth.log, IDS output)
  plus a journald source for the firewall log:
  `journalctl -k -f -o short-iso --cursor-file` (the journald cursor is the
  offset).  The firewall parser accepts rsyslog, `-o cat` and `-o short-iso`
  forms.
- **Heartbeat (3.7)** — every 30 s the agent POSTs `/api/agents/heartbeat`
  (API-key auth) with the IDS service status; `/api/stats` exposes agent and
  IDS health, which the Overview page renders.
- **Least privilege (3.8)** — runs as `mini-soc` (never root) with
  `SupplementaryGroups=adm mini-soc-ids systemd-journal`; the journal source
  needs the journal group, while log files and the IDS output need `adm` and
  `mini-soc-ids` respectively.

### 3.2 IDS/IPS (Phase 4 rewrite, spec §4.1)

`ids/live_ids_ips.py` replaces Suricata. It is **config-driven** — every
threshold, window, cooldown, allow-list, output path and hostname is read from
`/etc/mini-soc/ids.yaml` (`IDS_CONFIG`); a small set of `IDS_*`/`SOC_HOSTNAME`
environment variables (injected via the unit's `EnvironmentFile`) override
individual values, which is what the tests use to keep clocks small.

Detection:

- **Firewall input (port scan)** — every `SOC_DROP:` line from nftables is
  parsed for `SRC`/`DPT`; ≥ `scan.threshold` distinct destination ports from one
  source within `scan.window_sec` raises signature `9000001`.
- **SSH brute force** — failed logins are counted per source; ≥
  `ssh.threshold` within `ssh.window_sec` raises signature `9000002`.
- **SYN flood** — new inbound SYNs per source above `syn.threshold` within
  `syn.window_sec` raise signature `9000003` (the demo uses a modest rate; the
  signature is deliberately configurable rather than tuned for a real flood).
- **Unusual outbound** — each `SOC_OUT:` line for a destination port outside
  `outbound.allow_ports` raises signature `9000005` (`unusual_outbound`).
- **DNS anomaly** — a pure-stdlib `AF_PACKET` sniffer (`ids/dns_sniffer.py`)
  reads UDP/53 queries and raises signature `9000004` when a label is longer
  than `dns.max_label` or the query rate exceeds `dns.rate_per_min`. This is
  why the unit needs `CAP_NET_RAW` (and nothing else), and it can be disabled
  with `dns.enabled: false`.

Each alert is one line of Suricata-style JSON on `/var/log/mini_soc_ids.json`
(owned `mini-soc-ids:mini-soc`, `0640`), and every event carries the **raw**
line it came from so the collector retains it verbatim. There is a per-`(ip,
signature)` cooldown (`general.cooldown_sec`) so a scan does not emit one alert
per packet, and the allow-list (`allow_list.analyst_ips` +
`allow_list.approved_scanner_ips`) suppresses noise from known-good sources.

Prevention (task 4.7) is a separate, human-driven step:

- An analyst records a `block IP` response action on an incident
  (`POST /api/incidents/{id}/actions`).
- The dashboard shows a confirm dialog; on confirmation the backend calls
  `POST /api/actions/{id}/execute`, which validates the target (bare IPv4, not
  allow-listed — enforced in the backend **and** the helper) and runs
  `/usr/local/sbin/soc-block` through sudo.
- `deploy/sudoers/mini-soc-soc-block` lets the backend user run **only** that
  one script with no password (the backend unit therefore drops
  `NoNewPrivileges=yes`); the helper adds the address to the nftables
  `blocklist` set with a timeout. `POST /api/actions/{id}/unblock` reverses it.

## 4. Deployment architecture (AWS EC2)

The canonical layout (created by `deploy/install.sh`):

| Thing | Value |
|---|---|
| Code | `/home/ubuntu/mini-soc` |
| Venv | `/home/ubuntu/mini-soc/.venv` |
| Config | `/etc/mini-soc/.env` (0640, `root:mini-soc`) |
| Agent config | `/etc/mini-soc/agent.yaml` (0640, `root:mini-soc`) |
| IDS config | `/etc/mini-soc/ids.yaml` (0640, `root:mini-soc`) |
| Allow-list | `/etc/mini-soc/allowlist.txt` (0640, `root:mini-soc`, rendered from `ids.yaml`) |
| Block helper | `/usr/local/sbin/soc-block` + `/etc/sudoers.d/mini-soc-soc-block` |
| Firewall | `/etc/nftables.conf` (logs `SOC_DROP:`/`SOC_OUT:`, holds the `blocklist` set) |
| State | `/var/lib/mini-soc/{evidence,agent/spool}` + `agent/state.json` |
| Logs | journald (`journalctl -u soc-backend -f`) |
| Database | PostgreSQL 16 on `localhost:5432` |
| Units | `soc-backend`, `soc-collector`, `soc-detection`, `soc-agent`, `mini-soc-ids` |

- **One EC2 instance** (Ubuntu 24.04) runs everything: Nginx + PHP-FPM + MariaDB
  + DVWA (web target), sshd with a test account (SSH target), and the full SOC
  stack as systemd services. See `docs/lab-setup.md` for instance details.
- **Security Group** is the perimeter control: it decides what can reach the
  instance at all.  **nftables on the host** (`/etc/nftables.conf`, installed by
  `install.sh`) is the second layer: it logs what actually arrived (input drops
  as `SOC_DROP:`, new outbound connections as `SOC_OUT:` — the IDS's input),
  allows only 22/80/443 plus established/ICMP, and enforces the `blocklist` set
  the response-action helper writes.
  - Inbound: TCP 22 and 80 are open so the attack can reach the box from the
    internet, matching the spec's "only 22 and 80 allowed" rule.
  - The dashboard/API nginx endpoint (443, plus 80 redirect) and the API itself
    (bound to `127.0.0.1:8000`) are restricted to analyst IPs only, not opened to
    the world. See `docs/testing/` and the Security Group notes in `README.md`.
  - Outbound: default allow, or tightened per `docs/testing/` findings.  Only
    traffic that reaches the host is logged by nftables — the Security Group
    drops everything else before it arrives, so the two must be kept in sync.
- **No internal network segmentation** exists the way the original
  fw-01/lab-attack/lab-servers design had it — the Security Group is the only
  layer in that role. `live_ids_ips.py`'s host-level rules add a second layer.
- **The attacker (Kali) is a local VM on a laptop**, outside AWS, attacking the
  EC2 instance's **public IP** over the real internet. This means:
  - `src_ip` in alerts is the attacker's real public IP (dynamic, likely NATed),
    not a clean lab IP.
  - The false-positive demo needs a second, controlled source; the choice
    (a phone hotspot) and the method are recorded in
    `docs/testing/second-source-ip.md`.
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
| Intrusion detection/prevention | `ids/live_ids_ips.py` (custom Python daemon) | journal + AF_PACKET DNS detection; human-confirmed blocking via `soc-block` — replaces Suricata, see Sections 2 and 3.2 |
| Perimeter filtering | AWS Security Group + host nftables | SG decides what arrives; nftables logs it and enforces the blocklist — see Section 4 |
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
