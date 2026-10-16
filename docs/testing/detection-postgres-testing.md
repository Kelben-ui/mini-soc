# Detection Engine & PostgreSQL — EC2 Test Guide

Step-by-step verification of the **detection engine** (`detection/`) and
**PostgreSQL 16** on the Mini SOC EC2 instance, covering the offline replay
test, the live detection loop, alert creation/dedup, checkpoint persistence,
and database schema/migration state.

The detection engine reads new events from the database, matches them against
the YAML rules in `rules/`, and creates or updates alerts. Two modes are
exercised here:

- **Offline replay** (`detection/tests/replay_test.py`) — loads a bundled PCAP-
  derived event set (341 events), runs every rule against them in a throwaway
  SQLite DB (or the live Postgres with the service stopped), asserts alert
  creation, then cleans up after itself.
- **Live loop** (`detection/run.py`, run by `soc-detection.service`) — polls
  the database every 2 seconds (`DETECTION_POLL_SECONDS=2`), processes only
  events newer than its checkpoint, and writes
  `/var/lib/mini-soc/detection_checkpoint.json` after each run.

Run everything on the box, from the repo root.

> **Export `DATABASE_URL` in every new shell.** `/etc/mini-soc/.env` is
> `0640 root:mini-soc`, so the `ubuntu` user cannot read it directly. The
> `ENV_FILE=/dev/null` override below stops the app config from picking up a
> root-owned env file, and the `sudo grep` line pulls the live URL into your
> shell explicitly. **Do not run these tests with `sudo`** — as root,
> `mini_soc_config` would read the real `/etc/mini-soc/.env` on its own.

---

## 0. Setup

```bash
ssh ubuntu@<EC2-ELASTIC-IP>
cd /home/ubuntu/mini-soc

# pytest is a dev dependency; install.sh installs requirements.txt only.
.venv/bin/pip install -r requirements-dev.txt

# Re-define these after every new SSH session (they do not persist).
export ENV_FILE=/dev/null
export DATABASE_URL="$(sudo grep -E '^DATABASE_URL=' /etc/mini-soc/.env | cut -d= -f2-)"

# Read-only event-count helper. Re-define it after every new SSH session.
count() { sudo -u postgres psql -tA -d mini_soc -c "select count(*) from $1"; }
```

If a later step fails with `KeyError: 'DATABASE_URL'`, you opened a new shell
— re-run the two `export` lines.

> **Path note:** `.venv/bin/python` is resolved from the **repo root**
> (`/home/ubuntu/mini-soc`). If you are inside `backend/` or `detection/`, the
> relative path will not exist — `cd /home/ubuntu/mini-soc` first or use the
> absolute path `/home/ubuntu/mini-soc/.venv/bin/python`.

---

## Part A — PostgreSQL

### A1. Service is active

```bash
sudo systemctl status postgresql@16-main --no-pager | head -5
```

**Expected:**

```
● postgresql@16-main.service - PostgreSQL Cluster 16/main
     Loaded: loaded (/lib/systemd/system/postgresql@16-main.service; enabled)
     Active: active (running) since ...
```

### A2. Version and listen address

```bash
sudo -u postgres psql -tA -c "show server_version;"
sudo -u postgres psql -tA -c "show listen_addresses;"
```

**Expected:**

```
16.x (Debian 16.x-1.pgdg...)
localhost
```

`listen_addresses = 'localhost'` confirms the DB is **not** exposed beyond the
box — no public ingress, matching `deploy/postgres.sh`.

### A3. Role and database exist

```bash
sudo -u postgres psql -tAc "select rolname from pg_roles where rolname='mini_soc';"
sudo -u postgres psql -tAc "select datname from pg_database where datname='mini_soc';"
```

**Expected:** `mini_soc` printed by both queries.

### A4. Schema — 13 tables (12 model tables + `alembic_version`)

```bash
sudo -u postgres psql -d mini_soc -c "\dt"
```

**Expected:** 13 rows, including:

```
              List of relations
 Schema |       Name        | Type  |  Owner
--------+-------------------+-------+----------
 public | alerts            | table | mini_soc
 public | alembic_version   | table | mini_soc
 public | alert_events      | table | mini_soc
 public | chains            | table | mini_soc
 public | detection_rules   | table | mini_soc
 public | events            | table | mini_soc
 public | incidents         | table | mini_soc
 ...    | ...               | ...   | ...
```

(Plus `agents`, `audit_logs`, `response_actions`, `users`, `settings` —
12 model tables in total.)

### A5. Migrations at head

```bash
cd /home/ubuntu/mini-soc/backend
ENV_FILE=/dev/null DATABASE_URL="$DATABASE_URL" \
  /home/ubuntu/mini-soc/.venv/bin/alembic current
```

**Expected:**

```
d4e5f6a7b8c9 (head)
```

Anything other than `(head)` means pending migrations — run
`alembic upgrade head` with the same env before continuing.

### A6. App-role connectivity + baseline counts

```bash
.venv/bin/python - <<'EOF'
import os
import sqlalchemy as sa

eng = sa.create_engine(os.environ["DATABASE_URL"])
with eng.connect() as c:
    for t in ("events", "alerts", "alert_events", "incidents", "chains"):
        print(f"{t:14} {c.execute(sa.text(f'select count(*) from {t}')).scalar()}")
EOF
```

**Expected:** one line per table with integer counts. On a fresh box these may
be `0`; during this guide `events` will be non-zero (live agent traffic) and
`alerts` will grow in step B6. If this raises an auth or connection error, the
`DATABASE_URL` export is missing or stale — re-run step 0.

---

## Part B — Detection engine

### B1. Rule loading — 13 rules

```bash
cd /home/ubuntu/mini-soc
ENV_FILE=/dev/null DATABASE_URL="$DATABASE_URL" .venv/bin/python - <<'EOF'
from detection.engine.rule_loader import load_rules
rules = load_rules()
print(f"Loaded {len(rules)} rules")
for r in rules:
    print(f"  {r['id']:14} {r.get('severity', '?'):8} {r.get('name', '')}")
EOF
```

**Expected:** `Loaded 13 rules` and 13 rows.

> `rules/allowlist.yaml` has no `id:` field and is **skipped by design** — 13,
> not 14, is correct.

### B2. Offline replay (SQLite, fully isolated)

```bash
cd /home/ubuntu/mini-soc
ENV_FILE=/dev/null .venv/bin/python -m detection.tests.replay_test
```

**Expected (tail):**

```
Replaying 341 events against 13 rules ...
...
REPLAY TEST PASSED
```

Key assertions printed along the way:

- 341 events loaded, 13 rules loaded
- 13 alerts created (one per rule that fired)
- 341 alert↔event links
- 1 correlated chain
- cleanup ran (no `192.0.2.100` rows left behind)

This mode uses a throwaway SQLite DB — it never touches Postgres, so it is
safe to run while `soc-detection` is active.

### B3. Replay against live Postgres

> **Stop the service first.** The live loop polls every 2s and will race the
> replay for the injected events: it may link them into its own alert first,
> making the replay report "no alerts were created", or collide with cleanup.
> Restart the service afterwards.

```bash
sudo systemctl stop soc-detection

cd /home/ubuntu/mini-soc
ENV_FILE=/dev/null DATABASE_URL="$DATABASE_URL" \
  .venv/bin/python -m detection.tests.replay_test

sudo systemctl start soc-detection
```

**Expected:** same output as B2 — `REPLAY TEST PASSED` with 341 events, 13
alerts, 341 links.

**Zero-residue check:**

```bash
sudo -u postgres psql -tA -d mini_soc -c \
  "select count(*) from events where src_ip='192.0.2.100';"
```

**Expected:** `0` — the replay cleans up its own rows even in live-DB mode.

### B4. Live service health + startup banner

```bash
sudo systemctl status soc-detection --no-pager | head -5
sudo journalctl -u soc-detection --since "-15 min" --no-pager | tail -25
```

**Expected:** `Active: active (running)`, running as `User=mini-soc`, and a
startup banner containing:

```
Loaded N rules ...
Loaded checkpoint: {'last_event_timestamp': '2026-10-16T10:55:10+00:00', ..., 'alerts': []}
Detection loop started (poll every 2s)
```

> **Idle journal is quiet by design.** `run.py` only logs
> `Detection run complete: alert IDs %s` when it actually processed new
> events. An empty journal between events is normal, not a failure.

### B5. Checkpoint file

```bash
sudo cat /var/lib/mini-soc/detection_checkpoint.json
```

**Expected:** JSON with `last_event_timestamp`, `last_run`, and `alerts`
(e.g. `{"last_event_timestamp": "...+00:00", "last_run": "...", "alerts": []}`).
The file is written after every loop run.

### B6. Live end-to-end: inject failures → alert

Inject 10 failed-SSH auth lines from a single source IP via the collector
ingest API (port 9000, header `X-API-Key`) — this trips `SSH-BF-001`
(threshold: 10 failures / 300s, grouped by `src_ip`, severity HIGH):

```bash
export INGEST_KEY="$(sudo grep -E '^INGEST_KEY=' /etc/mini-soc/.env | cut -d= -f2-)"

for i in $(seq 1 10); do
  curl -s -X POST http://127.0.0.1:9000/ingest \
    -H "X-API-Key: $INGEST_KEY" \
    -H 'Content-Type: application/json' \
    -d '[{"source": "sshd", "line": "Failed password for invalid user admin from 198.51.100.44 port 4242 ssh2"}]'
  echo
done
```

**Expected:** each call returns roughly
`{"backend_status": 200, "backend_response": ..., "accepted": 1}`.

Wait ~5–10 seconds (the loop polls every 2s), then check:

```bash
sudo -u postgres psql -d mini_soc -c \
  "select id, rule_id, severity, status, src_ip, alert_data->>'count' as cnt
   from alerts order by id desc limit 3;"
sudo -u postgres psql -tA -d mini_soc -c \
  "select count(*) from alert_events where alert_id=(select max(id) from alerts);"
```

**Expected:** one new alert row —
`SSH-BF-001 | HIGH | NEW | 198.51.100.44 | cnt 10` — and exactly `10` links in
`alert_events`.

Confirm in the journal (use a **15-minute** window; the run line lands ~2s
after ingest and a 1-minute window often misses it):

```bash
sudo journalctl -u soc-detection --since "-15 min" --no-pager | grep 'Detection run complete'
```

**Expected:**

```
Detection run complete: alert IDs [117]
```

(The ID will differ on a box with prior test data.)

### B7. Dedup — same open alert is updated, not duplicated

Inject 5 more failures from the same IP (same command as B6 with `seq 1 5`),
wait ~5s, then:

```bash
sudo -u postgres psql -d mini_soc -c \
  "select id, rule_id, status, src_ip, alert_data->>'count' as cnt
   from alerts where rule_id='SSH-BF-001';"
```

**Expected:** **one** row — the same `id`, `status` still `NEW` (open), and
`cnt` now `15`. The engine dedups on open `(rule_id, src_ip, dst_ip)`
(`detection/engine/alert_manager.py`). **Two rows = failure.**

### B8. Restart persistence — checkpoint resumes, no duplicate alert

```bash
sudo systemctl restart soc-detection
sleep 5
sudo journalctl -u soc-detection --since "-5 min" --no-pager | grep 'Loaded checkpoint'
sudo -u postgres psql -tA -d mini_soc -c "select count(*) from alerts where rule_id='SSH-BF-001';"
```

**Expected:**

- The `Loaded checkpoint` line shows a `last_event_timestamp` from **after**
  your injections (i.e. the loop resumes where it left off, not at 0).
- Alert count is still `1` — restart does not reprocess old events into
  duplicate alerts.

### B9. Cleanup

Remove the injected test data in FK-safe order (events → alert → links):

```bash
sudo -u postgres psql -d mini_soc -c "delete from alert_events where alert_id=117;"
sudo -u postgres psql -d mini_soc -c "delete from alerts where id=117;"
sudo -u postgres psql -d mini_soc -c "delete from events where src_ip='198.51.100.44';"
```

(Adjust `117` to the actual alert ID from B6.)

**Expected:** `DELETE 10` (or 15) / `DELETE 1` / `DELETE 10` (or 15).

> Skipping cleanup is acceptable if you want to keep a demo alert for the
> dashboard — dedup (B7) and restart (B8) still pass with it present.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `KeyError: 'DATABASE_URL'` | New SSH shell — exports don't persist | Re-run step 0's `export` lines |
| `.venv/bin/python: No such file or directory` | Running from `backend/`/`detection/` | `cd /home/ubuntu/mini-soc` or use the absolute venv path |
| Replay vs live DB: "no alerts were created" | `soc-detection` raced the replay for the injected events | `sudo systemctl stop soc-detection`, re-run, `start` again |
| `alembic current` shows a revision ≠ `d4e5f6a7b8c9 (head)` | Pending migrations | `ENV_FILE=/dev/null DATABASE_URL="$DATABASE_URL" alembic upgrade head` |
| Journal grep for `Detection run complete` is empty | Time window too tight (line logs ~2s after ingest) | Use `--since "-15 min"` or check the checkpoint file |
| Journal silent between events | **By design** — the loop only logs when it processes new events | No fix needed; check `Loaded checkpoint` on startup instead |
| Ingest returns `422` | Batch accepted but no line parsed | Parser/format issue, not detection — see `agent-testing.md` |
| Ingest returns `401`/`403` | Missing/bad `X-API-Key` | Re-export `INGEST_KEY` from step B6 |
| Two `SSH-BF-001` rows after B7 | Dedup failed | Check `alert_manager.py` dedup key — open `(rule_id, src_ip, dst_ip)` |

---

## Pass criteria

| # | Check | Pass signal |
|---|---|---|
| A1 | PostgreSQL service | `active (running)`, enabled |
| A2 | Version / exposure | `16.x`, `listen_addresses = localhost` |
| A3 | Role + database | `mini_soc` in both queries |
| A4 | Schema | 13 tables (12 models + `alembic_version`) |
| A5 | Migrations | `d4e5f6a7b8c9 (head)` |
| A6 | App connectivity | Counts print for all 5 tables |
| B1 | Rule loading | `Loaded 13 rules` |
| B2 | Offline replay (SQLite) | `REPLAY TEST PASSED` — 341 events, 13 alerts, 341 links, chain=1 |
| B3 | Live-DB replay | `REPLAY TEST PASSED` + residue count `0` after restart |
| B4 | Live service | `active`, banner shows rules + checkpoint + loop start |
| B5 | Checkpoint file | JSON with `last_event_timestamp`, `last_run`, `alerts` |
| B6 | End-to-end alert | `SSH-BF-001` / HIGH / NEW, `cnt=10`, 10 links |
| B7 | Dedup | Still one row, `cnt=15`, status open |
| B8 | Restart | Checkpoint resumed, alert count still 1 |
| B9 | Cleanup | `DELETE` rows in FK-safe order (or intentional keep) |

---

## Known by-design behaviours

- **`allowlist.yaml` is skipped** — it has no `id:`, so `load_rules()` returns
  13 rules, not 14.
- **Idle journal silence** — the loop logs `Detection run complete` only when
  events were processed; nothing per-tick is normal.
- **Checkpoint granularity** — `last_event_timestamp` advances after each run;
  restarts resume from it, so old events never regenerate alerts.
- **Replay idempotency** — the replay deletes prior `192.0.2.100` rows on
  entry and cleans up on exit, so it can be run repeatedly.
- **`ENV_FILE=/dev/null` everywhere** — as root the app would read the real
  `/etc/mini-soc/.env` and touch live Postgres unintentionally; `ubuntu` needs
  the `sudo grep` export instead.
