# Deploy (`deploy/`)

Provisioning and operations for the single EC2 SOC instance. **This is the
source of truth for the host** — it renders the live files, including everything
snapshotted under [`../infrastructure/`](../infrastructure/).

## One-command install

```bash
sudo MINI_SOC_REPO_URL=https://github.com/Kelben-ui/mini-soc.git \
     bash deploy/install.sh
```

`install.sh` is **idempotent**. In one pass it:

1. installs OS packages (incl. **nftables**, nginx, Python) and Node 20;
2. clones/updates the repo to `/home/ubuntu/mini-soc` and builds the venv;
3. creates the `mini-soc` / `mini-soc-ids` users, `/etc/mini-soc`, and
   `/var/lib/mini-soc/{evidence,agent}`;
4. writes `/etc/mini-soc/.env` (0640) and `/etc/mini-soc/agent.yaml`;
5. provisions **PostgreSQL 16** (`postgres.sh`) and runs Alembic migrations;
6. builds the frontend (`npm ci && npm run build`);
7. renders and installs the systemd units + nginx site + TLS cert;
8. installs the IDS config/allow-list, the `soc-block` helper and its sudoers
   rule, and the host firewall (`nftables/mini-soc.conf` → `/etc/nftables.conf`);
9. removes legacy `mini-soc-*` units, enables and starts every service.

Key paths are overridable via environment variables (see the top of
`install.sh`).

> **Note:** `install.sh` targets EC2 and writes runtime config under
> `/etc/mini-soc/`. The live local lab keeps every runtime config in the repo
> instead (`<repo>/.env`, `agents/agent.yaml`, `ids/ids.yaml`,
> `rules/allowlist.txt`); only OS-owned artifacts (systemd units, nginx site,
> `nftables.conf`, TLS cert, sudoers rule) are installed system-wide.

## Update an existing host

```bash
sudo bash deploy/update.sh   # pull, deps, migrate, rebuild frontend, re-render units, restart
```

## Contents

| Path | Purpose |
|---|---|
| `install.sh` | Full idempotent bootstrap (above). |
| `update.sh` | Update an existing deployment. |
| `postgres.sh` | PostgreSQL 16 bootstrap: PGDG repo, localhost-only, role + DB from `DATABASE_URL`. |
| `soc-block` | Response-action helper (task 4.7). `add`/`del` an IPv4 in the nftables `blocklist` set; refuses non-IPv4 and allow-listed addresses. Runs via sudo only. |
| `sudoers/mini-soc-soc-block` | Restricts the backend user to exactly `soc-block` with no password. |
| `systemd/soc-backend.service` | Dashboard API (`uvicorn` on `127.0.0.1:8000`). |
| `systemd/soc-collector.service` | Normalization service (`127.0.0.1:9000`). |
| `systemd/soc-detection.service` | Detection engine loop (`python -m detection.run`). |
| `systemd/soc-agent.service` | Host log agent. |
| `systemd/mini-soc-ids.service` | Custom IDS/IPS daemon. |
| `nginx/mini-soc.conf` | Dashboard site on :443 (+ :80 redirect), the `soc` log format, `/api` proxy to the backend. |
| `nftables/mini-soc.conf` | Host firewall + telemetry (`SOC_DROP:`/`SOC_ACCEPT:`/`SOC_OUT:` logging) + `blocklist` set. |

## Services

```bash
systemctl status soc-backend soc-collector soc-detection soc-agent mini-soc-ids --no-pager
journalctl -u soc-detection -f
```

There is exactly **one** detection loop (the legacy `mini-soc-worker` was
removed), so alerts are never processed twice.

## Notes

- The installer does **not** set up DVWA, PHP-FPM, MariaDB or a custom `sshd`
  configuration — those are manual steps covered in
  [`../docs/lab-setup.md`](../docs/lab-setup.md).
- The dashboard listens on :443 with a self-signed cert by default; set
  `DOMAIN` for a real certificate.
