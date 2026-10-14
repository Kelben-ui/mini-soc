# Backend API — EC2 Test Guide

Step-by-step unit testing of the backend API (`backend/`) on the Mini SOC EC2
instance, covering the Phase 7 API contract (auth, alerts, incidents, chains,
users, rules/stats, response actions, agent heartbeat).

The suite is **55 tests across 8 files** and fully offline: it uses a throwaway
SQLite database (`backend-ci.db` in the repo root), calls the route functions
directly (no HTTP server, no `TestClient` — the pinned Starlette wants `httpx2`),
mocks the response-action helper, and never touches Postgres, the network, or
root.

Run everything on the box, from the repo root.

> **Do not run this suite with `sudo`.** As root, `mini_soc_config` reads the
> real `/etc/mini-soc/.env`, so `DATABASE_URL` would point at the live Postgres
> and the tests would write to it. Always use the `ENV_FILE=/dev/null` override
> below instead.

---

## 0. Setup

```bash
ssh ubuntu@<EC2-ELASTIC-IP>
cd /home/ubuntu/mini-soc

# pytest is a dev dependency; install.sh installs requirements.txt only.
.venv/bin/pip install -r requirements-dev.txt
```

**Why `ENV_FILE=/dev/null`:** `backend/app/database.py` imports
`mini_soc_config`, which loads `/etc/mini-soc/.env` (0640 `root:mini-soc`) —
unreadable by `ubuntu`, so `dotenv` raises `PermissionError`. Overriding
`ENV_FILE` skips it, and `backend/tests/conftest.py` supplies its own
`DATABASE_URL=sqlite:///./backend-ci.db`, `INGEST_API_KEY=test-key`,
`JWT_SECRET_KEY=test-secret`.

## 1. Run the whole backend suite

```bash
cd /home/ubuntu/mini-soc
ENV_FILE=/dev/null PYTHONPATH=. .venv/bin/python -m pytest backend -q
```

Expected:
```
55 passed, 53 warnings in ~12s
```

The warnings are deprecations (SQLAlchemy/JWT `utcnow()`), not failures.

## 2. Run file by file

```bash
ENV_FILE=/dev/null PYTHONPATH=. .venv/bin/python -m pytest backend/tests/test_actions_route.py   -q   # 11 passed
ENV_FILE=/dev/null PYTHONPATH=. .venv/bin/python -m pytest backend/tests/test_security.py        -q   # 11 passed
ENV_FILE=/dev/null PYTHONPATH=. .venv/bin/python -m pytest backend/tests/test_incident_detail.py -q   #  8 passed
ENV_FILE=/dev/null PYTHONPATH=. .venv/bin/python -m pytest backend/tests/test_alerts_route.py    -q   #  7 passed
ENV_FILE=/dev/null PYTHONPATH=. .venv/bin/python -m pytest backend/tests/test_users_route.py     -q   #  6 passed
ENV_FILE=/dev/null PYTHONPATH=. .venv/bin/python -m pytest backend/tests/test_chains_route.py    -q   #  5 passed
ENV_FILE=/dev/null PYTHONPATH=. .venv/bin/python -m pytest backend/tests/test_rules_stats.py     -q   #  4 passed
ENV_FILE=/dev/null PYTHONPATH=. .venv/bin/python -m pytest backend/tests/test_agents_route.py    -q   #  3 passed
```

| File | Tests | Covers |
|---|---|---|
| `test_actions_route.py` | 11 | execute/unblock via a fake `soc-block` helper, confirmation/IP/allowlist checks, IPv4-injection resistance |
| `test_security.py` | 11 | authz on routes, JWT expiry, bad-credential login, evidence path outside webroot, password policy, IPS validation |
| `test_incident_detail.py` | 8 | time-to-detect, notes, evidence/custody listing, merged timeline, assignment + status-transition rules |
| `test_alerts_route.py` | 7 | pagination envelope, severity/status/IP/time filters, detail with linked events, promote-to-incident, stats |
| `test_users_route.py` | 6 | create/list, duplicate rejection, invalid role, self-role-change block, last-admin protection, password reset |
| `test_chains_route.py` | 5 | chain grouping, detail ordering, unknown→404, promote-all-alerts, duplicate-promote rejection |
| `test_rules_stats.py` | 4 | rule fire-count enrichment, threat-level from active critical, response-time metrics |
| `test_agents_route.py` | 3 | heartbeat API-key auth + upsert, agent/IDS health stats |

## 3. Focused runs while debugging

```bash
ENV_FILE=/dev/null PYTHONPATH=. .venv/bin/python -m pytest backend -q -k users    # only user-management tests
ENV_FILE=/dev/null PYTHONPATH=. .venv/bin/python -m pytest backend -v             # per-test names
ENV_FILE=/dev/null PYTHONPATH=. .venv/bin/python -m pytest backend -x             # stop at first failure
```

## 4. Sanity-check collection

```bash
ENV_FILE=/dev/null PYTHONPATH=. .venv/bin/python -m pytest backend --collect-only -q | tail -2
```

Expected:
```
55 tests collected in ~0.4s
```

## 5. Optional: full CI parity

```bash
cd /home/ubuntu/mini-soc
ENV_FILE=/dev/null PYTHONPATH=. .venv/bin/python -m pytest -q ids backend collector agents
```

Expected: `132 passed`.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `No module named pytest` | `.venv/bin/pip install -r requirements-dev.txt` (step 0). |
| `PermissionError: ... /etc/mini-soc/.env` | Add `ENV_FILE=/dev/null` (never run this suite as root). |
| `ModuleNotFoundError: No module named 'backend'` | Run from the repo root and keep `PYTHONPATH=.`. |
| Tests seem to touch real data | `DATABASE_URL` leaked into your shell. `unset DATABASE_URL`, drop any `sudo`, and rerun. |
| `backend-ci.db` appears in the repo root | Expected — conftest recreates it per session; safe to delete. |

## Pass criteria

| Area | Coverage | Pass |
|---|---|---|
| Auth + authorization (JWT, roles, 401/403) | `test_security.py`, `test_agents_route.py` | ☐ |
| Users management + password policy | `test_users_route.py`, `test_security.py` | ☐ |
| Alerts (filters, pagination, promote) | `test_alerts_route.py` | ☐ |
| Incidents (detail, notes, timeline, status) | `test_incident_detail.py` | ☐ |
| Attack chains | `test_chains_route.py` | ☐ |
| Rules + stats metrics | `test_rules_stats.py` | ☐ |
| Response actions (block/unblock, allow-list) | `test_actions_route.py` | ☐ |
| Full suite green (55 passed) | step 1 | ☐ |

## Known by-design behaviours

- The tests call route functions **directly** with a `Session` fixture; they do
  not exercise the HTTP layer or `TestClient` (the pinned Starlette expects
  `httpx2`). Request validation that lives in FastAPI's signature is therefore
  covered by the route-level guards the tests call explicitly.
- The database is a throwaway SQLite file created/dropped per session; no
  Postgres data and no running service is contacted, so the suite is safe to run
  repeatedly, even with services live.
