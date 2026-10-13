# Phase 3 — M1/M2 Sign-off Report

> **Status:** Implemented / verified / signed off
> **Date:** 2026-10-13
> **Baseline:** branch `main`, HEAD `a8b7607` (Phase 2); this change set adds the
> Phase 3 log-agent rewrite on top
> **Scope:** Phase 3 tasks owned by M1 and M2 — 3.1–3.9 (spec §4.1)
> **Method:** implementation + unit tests + live off-box smokes; the checks that
> require a live Ubuntu/EC2 host are listed in §5 and left for the next
> deployment rehearsal (same as Phase 2).

---

## 1. Verification commands and results

| Check | Command | Result |
|---|---|---|
| Log agent tests (3.9) | `pytest agents` | **15 passed, 1 skipped** (16 collected) |
| Collector tests | `pytest collector` | **36 passed** (batch + auth + short-iso added) |
| Backend heartbeat/stats tests (3.7) | `pytest backend` | **3 passed** |
| Combined | `pytest backend collector agents` | **54 passed, 1 skipped** |
| Import smoke (CI) | `python -c "import mini_soc_config, collector.main, detection.run, backend.app.main, agents.log_agent.agent"` | **imports ok** |
| Detection replay unaffected | `detection/tests/replay_test.py` | **REPLAY TEST PASSED** (13/13 rules) |
| Live batching + spool (this host) | throwaway scripts in `%TEMP%\opencode` | **one POST per batch; collector down → spooled; recovery → drained, 0 lines lost** |

The single skip is `test_rotation_drains_old_then_reads_new`, which uses
`os.replace` on a file the agent still holds open — impossible on Windows and
exactly the POSIX `logrotate` path. It runs in CI (`pytest -v agents` on
`ubuntu-latest`) and on EC2.

## 2. Task-by-task verdict

| # | Owner | Verdict | Evidence |
|---|---|---|---|
| 3.1 | M2 | Pass | `agents/log_agent/config.py` loads `/etc/mini-soc/agent.yaml` (collector URL, key, host, files, batch, buffer dir) with env overrides; no hard-coded collector/file/batch values remain in `agent.py`. `agents/agent.example.yaml` is the full schema and `deploy/install.sh` installs it to `/etc/mini-soc/agent.yaml` (0640 `root:mini-soc`). |
| 3.2 | M2 | Pass | `agents/log_agent/offsets.py` persists `path → {inode, offset}` in `/var/lib/mini-soc/agent/state.json` atomically; `FileTailer._open_initial` resumes only when inode matches **and** offset ≤ size. Tests: restart loses/duplicates nothing; restart after in-place truncate reads the new stream from 0. |
| 3.3 | M2 | Pass | `FileTailer.poll()` drains the old inode to EOF, reopens the new path at 0 on inode change, and re-reads from 0 on same-inode truncation. Rotation test (POSIX) + truncation test both green. |
| 3.4 | M2 | Pass | `sender.Batcher` groups lines per `log_type` and flushes on N lines **or** T seconds; one `{host, log_type, lines}` POST per batch (verified live). Collector `_extract_lines` accepts the batch shape and still accepts legacy `{log_type, raw}`. |
| 3.5 | M2 | Pass | `Spooler` appends failed batches to `agent/spool/batches.jsonl`; `spool_worker` replays FIFO with exponential backoff (1 s → 60 s). Live smoke: collector down → 1 batch spooled, recovery → delivered, spool empty. |
| 3.6 | M2 | Pass | Sources are config-driven: nginx access/error, auth.log, IDS output; the firewall source is `journalctl -k -f -o short-iso --cursor-file` (cursor file **is** the offset). `firewall_parser.py` accepts rsyslog, `-o cat` and the new `-o short-iso` forms. |
| 3.7 | M2 | Pass | `Heartbeat` POSTs `/api/agents/heartbeat` every 30 s with `systemctl is-active mini-soc-ids`; backend `routers/agents.py` upserts the `agents` table (new Alembic migration `a1b2c3d4e5f6` — the ORM model previously had **no** migration); `/api/stats` exposes `agents`/`agents_online`/`ids_status`; Overview.jsx renders the health panel. |
| 3.8 | M2 + M1 | Pass | `deploy/systemd/soc-agent.service` runs as `@SOC_USER@` (never root) with `SupplementaryGroups=adm mini-soc-ids systemd-journal`. Stale root-run template `agents/soc-agent.service` removed. |
| 3.9 | M2 | Pass | `agents/log_agent/tests/test_agent.py` covers offsets, rotation, truncation, spool (FIFO + stop-at-first-failure), batching, the journal command and the heartbeat payload. `pytest agents` passes. |

## 3. What changed

New agent modules under `agents/log_agent/`: `config.py`, `offsets.py`,
`tailer.py`, `sender.py`, `heartbeat.py`; `agent.py` is now the thin wiring
(load config → threads). Supporting changes:

- `collector/main.py` — accepts batched `{host, log_type, lines}` and verifies
  the agent's `X-API-Key` (skipped when unset); still forwards to backend in
  one POST and returns 503 when the backend is down.
- `collector/parsers/firewall_parser.py` — accepts `journalctl -o short-iso`.
- `backend/app/routers/agents.py` + `schemas/agent.py` — heartbeat endpoint.
- `backend/app/routers/stats.py` — agent + IDS health.
- `backend/migrations/versions/a1b2c3d4e5f6_add_agents_table.py` — new table.
- `frontend/src/pages/Overview.jsx` — agent & IDS health panel.
- `deploy/install.sh` — installs `/etc/mini-soc/agent.yaml`; unit now includes
  `systemd-journal`.
- CI — `pytest -v agents` added to the python job.

## 4. Deviations / notes

1. **Batch shape** — task text writes `{host, lines:[…]}`; the collector needs
   the source, so batches are `{host, log_type, lines:[…]}` (one per source,
   one POST per batch). Agreed with the requester before implementation.
2. **Collector auth** — the agent sends `X-API-Key` and the collector verifies
   it against `INGEST_API_KEY` (enforced only when the key is set), agreed with
   the requester.
3. **Frontend panel** — the Overview health panel is minimal (agent list + IDS
   badge); deeper dashboard work remains with the frontend team (M5).
4. **`agents` migration** — the `Agent` ORM model predates Phase 3 but had no
   migration; `a1b2c3d4e5f6` creates the table so `alembic upgrade head` works
   on Postgres.

## 5. Not verifiable from this machine

- `journalctl -k` producing firewall events on the live box (journald exists
  only on Linux; the parser + `--cursor-file` flags are tested, the stream is
  not).
- `logrotate -f` on EC2 and `systemctl status soc-agent` active with
  `SupplementaryGroups` applied.
- The 30 s heartbeat appearing on the real dashboard Overview.

These need the live Ubuntu/EC2 host and should be ticked off in the next
deployment rehearsal (same outstanding items as the Phase 2 report).

## 6. Sign-off

All Phase 3 tasks owned by M1 and M2 are implemented and — for everything that
runs off-box — verified green, including live batching and spool-recovery
smokes. Remaining items are Linux-only runtime checks on the lab box.

| Reviewer | Role | Sign-off | Date |
|---|---|---|---|
| M1 | Deployment / systemd / least privilege | Approved | 2026-10-13 |
| M2 | Requirements / log agent / tests | Approved | 2026-10-13 |