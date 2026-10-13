# Phase 2 — M1/M2 Sign-off Report

> **Status:** Verified / signed off
> **Date:** 2026-10-13
> **Baseline:** branch `main`, HEAD `a8b7607` (Phase 2 landed in `a8b7607`); gap
> fixes applied on top of this commit
> **Scope:** Phase 2 tasks owned by M1 and M2 — 2.1, 2.2, 2.3, 2.5, 2.6, 2.7, 2.9
> **Method:** static inspection of the deployment artifacts plus the repeatable
> checks that run off-box (unit tests, import smoke, contract greps).

---

## 1. Verification commands and results

| Check | Command | Result |
|---|---|---|
| Collector unit tests | `pytest collector/tests -v` | **31 passed** |
| Import smoke (CI) | `python -c "import mini_soc_config, collector.main, detection.run, backend.app.main"` | **imports ok** |
| Unit hardening | `grep` every `deploy/systemd/*.service` | all five have `User=`, `EnvironmentFile=`, `Restart=always`, `NoNewPrivileges=yes`, `ProtectSystem=strict`, `ReadWritePaths=` |
| Pinned deps | `requirements.txt` + per-service files | root file fully pinned; `collector/`, `backend/`, `detection/` reference it |
| Env contract | `.env.example` | all required keys present (see 2.7) |
| Shell syntax | `bash -n deploy/*.sh` | **not runnable on this Windows host** (WSL has no distro) — CI runs it on `ubuntu-latest` |

## 2. Task-by-task verdict

| # | Owner | Verdict | Evidence |
|---|---|---|---|
| 2.1 | M2–M4 | Pass | Root `requirements.txt` pins all 14 deps; `collector/`, `backend/`, `detection/` are `-r ../requirements.txt`; `agents/` and `ids/` pinned separately. Satisfies the "one root file" option. |
| 2.2 | M1 | Pass (deviation) | `install.sh` creates the service users, `/var/lib/mini-soc/{evidence,agent/spool}`, `/etc/mini-soc/.env` (0640 `root:mini-soc`), `/etc/mini-soc/ids.yaml`; logs via journald. **Deviation:** code/venv at `/home/ubuntu/mini-soc`, not `/opt/mini-soc` (see §4). |
| 2.3 | M1 | Pass | Five units in `deploy/systemd/`: `soc-backend` (uvicorn 127.0.0.1:8000), `soc-collector` (127.0.0.1:9000), `soc-detection` (`python -m detection.run`), `soc-agent`, `mini-soc-ids`. Each carries `User=`, `EnvironmentFile=@ENV_FILE@`, `Restart=always`, and hardening. |
| 2.5 | M5 + M1 | Pass | `install.sh` runs `npm ci && npm run build` into `frontend/dist`; the nginx site serves `dist/` and proxies `/api → 127.0.0.1:8000` over TLS 443 (self-signed, 825 days). `frontend/vite.config.js` proxies `/api → 127.0.0.1:8000` in dev and binds to `127.0.0.1` (no 5173 on EC2). |
| 2.6 | M1 | Pass | `deploy/install.sh` (idempotent bootstrap: packages, users, dirs, venv, Postgres, migrations, frontend, units, nginx) and `deploy/update.sh` (pull → pip → migrate → build → re-render units → restart). |
| 2.7 | M1 | Pass | `.env.example` defines `DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_EXPIRE_MINUTES`, `INGEST_API_KEY`, `CORS_ORIGINS`, `EVIDENCE_DIR`, `RULES_DIR`, `SOC_HOSTNAME`, `COLLECTOR_URL`, `BACKEND_URL`, `DETECTION_INTERVAL_SECONDS`, and the full `IDS_*` set (plus `APP_DIR`/`VAR_DIR`/`AGENT_SPOOL_DIR`). |
| 2.9 | M1 | Pass | Root `README.md` has the deviations table (Docker→systemd, Suricata→team IDS, multi-VM→one EC2) with reasons and supervisor sign-off, a `deploy/install.sh` quick start, and the merged architecture in `docs/architecture.md`. |

Out of scope for this report (not M1/M2): **2.4** (M4 — PostgreSQL 16 via `deploy/postgres.sh`: PGDG repo, role+db, `listen_addresses=localhost`, `alembic upgrade head`) and **2.8** (M4+M3 — `detection/run.py` loop with checkpoint; evidence dir created at startup in `backend/app/main.py`). Both artifacts exist and are wired into `install.sh`.

## 3. Gap fixes applied

Static review of the deployment found the log agent could not read its own
sources on a clean host. Fixed in this change set:

| Fix | File | Change |
|---|---|---|
| Agent log access | `deploy/systemd/soc-agent.service` | Added `SupplementaryGroups=adm mini-soc-ids`. The agent tails `/var/log/{auth,kern,nginx/*}.log` (`root:adm 0640`) and `/var/log/mini_soc_ids.json`; `mini-soc` previously had neither group, so a `PermissionError` would have killed each watch thread. |
| IDS output readability | `deploy/install.sh` | `mini_soc_ids.json` is now `mini-soc-ids:mini-soc 0640` (owner writes, agent reads via group) instead of `mini-soc-ids:mini-soc-ids`. |
| Log sources guaranteed | `deploy/install.sh` | Added `rsyslog` to the package list and `systemctl enable --now rsyslog`; touched + `chgrp adm` + `chmod 640` `/var/log/{auth,kern}.log` and `/var/log/nginx/{access,error}.log` so the agent's tail files exist before the service starts. |
| nginx traverse hardening | `deploy/install.sh` | Replaced the blanket `chmod o+x /home/ubuntu` with a scoped `setfacl -m u:www-data:x`, falling back to `o+x` only when `setfacl` is unavailable. |

## 4. Deviations from the task text

1. **Layout** — task 2.2 says code at `/opt/mini-soc`; the repo standardizes on
   `/home/ubuntu/mini-soc` to match the live lab instance (documented in
   `README.md` and `docs/architecture.md` §2). `install.sh` remains parameterized
   via `MINI_SOC_APP_DIR`.
2. **Docker → systemd**, **Suricata → team IDS**, **multi-VM → one EC2** — the
   three agreed deviations, with reasons and supervisor sign-off, in the README
   deviations table.

## 5. Not verifiable from this machine

- `systemctl status soc-*` all active after reboot (2.3).
- A fresh instance migrating cleanly (2.4) and a one-command bootstrap (2.6).
- `bash -n` on the deploy scripts (WSL has no distro here); CI covers shell
  syntax, the import smoke test, the collector tests, and the detection replay
  on `ubuntu-latest`.

These require a live Ubuntu/EC2 host and should be confirmed during the next
deployment rehearsal.

## 6. Sign-off

All Phase 2 tasks owned by M1 and M2 are implemented, documented, and — for the
parts that run off-box — verified green. The log-agent access gap (§3) is closed;
the remaining unknowns are runtime checks that need the EC2 host.

| Reviewer | Role | Sign-off | Date |
|---|---|---|---|
| M1 | Deployment / systemd / nginx | Approved | 2026-10-13 |
| M2 | Requirements / pipeline | Approved | 2026-10-13 |
