# Phase 2 — M1/M2 Sign-off Report

> **Status:** Verified / signed off
> **Date:** 2026-10-13
> **Baseline:** branch `main`, HEAD `a8b7607` (Phase 2 landed in `a8b7607`); gap
> fixes applied on top of this commit
> **Scope:** Phase 2 tasks for all members — M1/M2 tasks 2.1, 2.2, 2.3, 2.5,
> 2.6, 2.7, 2.9 in §1-§6, plus **2.4 (M4)**, **2.5 (M5)** and **2.8 (M4+M3)**
> in the all-member addendum in §7.
> **Method:** static inspection of the deployment artifacts plus the repeatable
> checks that run off-box (unit tests, import smoke, contract greps).

---

## 1. Verification commands and results

| Check | Command | Result |
|---|---|---|
| Collector unit tests | `pytest collector/tests -v` | **31 passed** |
| Import smoke (CI) | `python -c "import mini_soc_config, collector.main, detection.run, backend.app.main"` | **imports ok** |
| Unit hardening | `grep` every `deploy/systemd/*.service` | all five have `User=`, `EnvironmentFile=`, `Restart=always`, `ProtectSystem=strict`, `ReadWritePaths=`; **four** have `NoNewPrivileges=yes` — `soc-backend` is the deliberate exception (it runs the sudo-confined `soc-block` helper, task 4.7) |
| Pinned deps | `requirements.txt` + per-service files | root file fully pinned (16 deps); `collector/`, `backend/`, `detection/` reference it; `agents/log_agent/` and `ids/` pin their own runtimes |
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

---

## 7. All-member re-verification (2026-10-14)

§1–§6 covered only the M1/M2-owned tasks and left **2.4 (M4)**, **2.5 (M5)** and
**2.8 (M4+M3)** out of scope. This addendum closes those gaps for all members,
re-verified on branch `main` on top of `eab8c4a`, clean working tree.

### 7.1 Verification commands and results

| Check | Command | Result |
|---|---|---|
| Combined unit tests | `pytest ids backend collector agents -q` | **86 passed, 1 skipped** |
| Detection replay (13 rules) | `python detection/tests/replay_test.py` | **REPLAY TEST PASSED** — 13/13 |
| Migration chain (2.4) | `alembic heads` / `alembic history` | single linear head `b2c3d4e5f6a7`, 6 revisions, `base → head` |
| Migration DDL (2.4) | `alembic upgrade head` on SQLite | **expected failure** — `588042e3de4c` uses `ALTER COLUMN … SET NOT NULL`, Postgres-only; the migration path is therefore exercised against PostgreSQL (what `install.sh` provisions) |
| Frontend production build (2.5) | `npm ci && npm run build` | `npm ci` → 0 vulnerabilities; `vite build` → `dist/` (95 modules, 336.82 kB JS / 21.63 kB CSS) |
| Rules load with no CWD (2.8) | `load_rules()` from `%TEMP%` | **13 rules** — loading no longer depends on the working directory |

### 7.2 All-member task verdicts

| # | Owner | Verdict | Evidence |
|---|---|---|---|
| 2.1 | M2–M4 | Pass | Root `requirements.txt` (16 pinned deps); `collector/`, `backend/`, `detection/` are `-r ../requirements.txt`; `agents/log_agent/requirements.txt` and `ids/requirements.txt` pin their own runtimes; `requirements-dev.txt` adds pytest. |
| 2.4 | M4 | Pass (off-box) | `deploy/postgres.sh`: PGDG repo, `postgresql-16`, `listen_addresses = 'localhost'` (via `conf.d/mini-soc.conf`), role + database parsed from `DATABASE_URL`; `install.sh` runs `alembic upgrade head`. Migration chain is a single linear head. _The on-Postgres migration itself still needs the rehearsal (§7.3)._ |
| 2.5 | M5+M1 | Pass | `npm ci && npm run build` succeeds → `dist/`; nginx serves `@APP_DIR@/frontend/dist` and proxies `/api` → `127.0.0.1:8000` (no trailing slash); Vite dev binds `127.0.0.1:5173` (no dashboard port exposed on EC2). |
| 2.8 | M4+M3 | Pass | Backend creates `EVIDENCE_DIR` at startup (`backend/app/main.py`); `alerts.py` now uses the shared `evidence_dir()` helper; `detection/run.py` polls at `DETECTION_POLL_SECONDS` with a checkpoint. **Fixed** the last CWD-relative path: `detection/engine/rule_loader.load_rules()` now defaults to the absolute `RULES_DIR` (falling back to `<repo>/rules`), verified by loading 13 rules from `%TEMP%`. |

### 7.3 Still on-box only

Unchanged from §5: `systemctl status soc-*` after a reboot, a fresh-instance
`install.sh`/`postgres.sh` run plus `alembic upgrade head` against PostgreSQL, and
`bash -n` on the deploy scripts (CI does this on `ubuntu-latest`).

### 7.4 All-member sign-off

| Reviewer | Role | Sign-off | Date |
|---|---|---|---|
| M3 | Detection rules / replay | Approved | 2026-10-14 |
| M4 | Backend / database / migrations | Approved | 2026-10-14 |
| M5 | Frontend / build / nginx | Approved | 2026-10-14 |
