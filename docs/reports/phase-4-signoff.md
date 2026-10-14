# Phase 4 — M1/M2 Sign-off Report

> **Status:** Implemented / verified / signed off
> **Date:** 2026-10-14
> **Baseline:** branch `main`, HEAD `4cf8d89` (Phase 4 landed in `4cf8d89`), clean working tree
> **Scope:** Phase 4 tasks 4.1–4.11 — the custom IDS/IPS that replaces Suricata. The
> IDS itself, its systemd unit, the deployment side of task 4.7 (`soc-block`,
> sudoers, nftables `blocklist`) and the unit tests are M1/M2-owned. The task 4.7
> backend endpoint (M4) and dashboard confirm flow (M5) are out of scope for this
> report but confirmed present and tested (see §2).
> **Method:** code inspection plus repeatable test runs. Verification only — no
> source changes were made to produce this report (the Phase 4 change set itself
> is commit `4cf8d89`).

---

## 1. Verification commands and results

| Check | Command | Result |
|---|---|---|
| IDS unit tests (4.10) | `pytest ids -q` | **21 passed** |
| Backend tests (incl. 4.7 routes) | `pytest backend -q` | **14 passed** |
| Collector tests | `pytest collector -q` | **36 passed** |
| Log-agent tests | `pytest agents -q` | **15 passed, 1 skipped** (POSIX-only rotation test) |
| Combined | `pytest backend collector agents ids detection -q` | **86 passed, 1 skipped** |
| Import smoke (CI) | `python -c "import mini_soc_config, collector.main, detection.run, backend.app.main, agents.log_agent.agent, ids.config, ids.live_ids_ips, ids.dns_sniffer"` | **imports ok** |
| End-to-end detection | `DATABASE_URL=sqlite:///./ci-replay.db PYTHONPATH=. python detection/tests/replay_test.py` | **REPLAY TEST PASSED** — 13/13 rules fired, including `NET-OUTBOUND-001` and `DNS-ANOMALY-001` |

The single skip is `test_rotation_drains_old_then_reads_new` (`agents`), which uses
`os.replace` on a file the agent still holds open — impossible on Windows and
exactly the POSIX `logrotate` path. It runs in CI (`ubuntu-latest`) and on EC2.

## 2. Task-by-task verdict

| # | Owner | Verdict | Evidence |
|---|---|---|---|
| 4.1 | M1 + M2 | Pass | The old detector only matched `NMAP_SCAN_PROBE` while the host firewall logged `SOC_DROP:` — the bug this task names. `ids/config.py` now makes both prefixes configurable (`IDS_PREFIX_SOC_DROP`, `ids.yaml`) and `ids/live_ids_ips.py` matches `SOC_DROP:` plus the `NMAP_SCAN_PROBE` marker. `attack-sim/port-scan.sh` produces the scan alert; covered by `test_prefix_is_configurable`. |
| 4.2 | M2 | Pass | `ids/ids.yaml` (installed to `/etc/mini-soc/ids.yaml`) carries every threshold, window, cooldown, allow-list, output path, hostname and signature; `ids/config.py` resolves YAML + `IDS_*` env overrides with no hard-coded constants left in `live_ids_ips.py`. |
| 4.3 | M2 | Pass | Docstrings and `ids/README.md` match the code: it writes `/var/log/mini_soc_ids.json` and is **detection-only** until task 4.7 (blocking is a separate, human-confirmed step); the firewall source uses `journalctl -o short-iso` so the raw line keeps its timestamp. |
| 4.4 | M2 | Pass | `deploy/nftables/mini-soc.conf` logs new outbound connections (`SOC_OUT:`) from the output chain; the IDS raises `outbound_connection` for ports not on the allow-list (53/80/443/123…) and the collector maps it to `network`/`unusual_outbound`. `rules/unusual_outbound.yaml` (`NET-OUTBOUND-001`) fires in the replay run; `attack-sim/outbound-conn.sh` is the M3 probe. |
| 4.5 | M2 | Pass | `ids/dns_sniffer.py` sniffs UDP/53 via `AF_PACKET` and emits `dns_query` events with query name, length and rate; long labels (>50 chars) and high rates (>100/min) are flagged as `unusual_dns`. `rules/unusual_dns.yaml` (`DNS-ANOMALY-001`) fires in the replay run; `attack-sim/dns-tunnel-sim.sh` is the M3 probe. |
| 4.6 | M2 | Pass | Optional `SYN flood` signature (9000003) with a configurable rate, plus the scanner-UA signature, are implemented and config-driven. |
| 4.7 | M1 + M2 (+ M4/M5) | Pass | `deploy/soc-block {add,del} <ip> [timeout]` validates IPv4 and refuses allow-listed IPs; `deploy/sudoers/mini-soc-soc-block` lets only the backend user run it; the nftables `blocklist` set (`flags timeout`) is dropped via `ip saddr @blocklist drop`. `backend/app/ips.py` + `routers/actions.py` expose `POST /api/actions/{id}/execute` (confirm-gated, records result, audited) and an unblock; `frontend/src/pages/IncidentDetail.jsx` implements the confirm dialog and Unblock. Backend route tests pass (`backend/tests/test_actions_route.py`). |
| 4.8 | M2 | Pass | `IdsEngine._prune` evicts idle IPs from `scan_hits`/`ssh_hits` so memory is bounded; covered by a unit test. |
| 4.9 | M1 | Pass | `deploy/systemd/mini-soc-ids.service` runs as the dedicated `mini-soc-ids` user with `SupplementaryGroups=systemd-journal adm`, `AmbientCapabilities=CAP_NET_RAW` (needed only for DNS sniffing) and the standard hardening — never root. |
| 4.10 | M2 | Pass | `ids/tests/test_ids.py` — 21 tests over `parse_line`, thresholds, cooldown, allow-list (fed fake journal lines), DNS parsing and pruning. `pytest ids` passes. |
| 4.11 | M2 | Pass | The detector now lives in `ids/` (`live_ids_ips.py`, `config.py`, `dns_sniffer.py`, `ids.yaml`, `README.md`) with a README documenting protocols monitored, signatures (id/msg/priority), output format and config; the old `infrastructure/fw-01/` files were retired. |

Out of scope for this report (not M1/M2): the M4 backend action endpoints
(`backend/app/routers/actions.py`, `backend/app/ips.py`, migration
`b2c3d4e5f6a7`) and the M5 dashboard confirm flow
(`frontend/src/pages/IncidentDetail.jsx`). Both exist and are exercised by
`backend/tests/test_actions_route.py`.

## 3. Notes and deviations

1. **Port-scan threshold.** The spec (`docs/rules.md` §3.10), the playbook and
   `attack-sim/README.md` all state **≥20 distinct destination ports/min**, and
   the pre-Phase 4 code used `SCAN_PORTS = 20`. The initial Phase 4 config shipped
   `15`; this was aligned to **20** in `ids/ids.yaml`, `ids/config.py` (the
   `IDS_SCAN_THRESHOLD` default), `.env.example` and `ids/README.md` so docs and
   code agree (task 4.3).
2. **Detection-only vs prevention.** Task 4.3 says "detection-only until 4.7".
   The IDS process remains detection-only at all times; prevention is a separate,
   human-confirmed `soc-block` invocation driven by the backend, exactly as 4.7
   specifies.
3. **Collector mapping.** The IDS emits `event_type` values `dns_query` /
   `outbound_connection`; the collector normalizes them to the frozen contract's
   `dns`/`unusual_dns` and `network`/`unusual_outbound` actions (§2.6). This is
   intended, not a mismatch.

## 4. Not verifiable from this machine

- Running `attack-sim/{port-scan,outbound-conn,dns-tunnel-sim}.sh` against the
  live box and observing the specific rule fire (the parser + rule + replay paths
  are tested; the on-wire trigger needs the host).
- Demo step 8 end to end: confirm → `soc-block` adds the IP → the next attempt
  is dropped by nftables → the action appears in the incident timeline and audit
  log. The code path is unit-tested; the live nftables effect needs root on Linux.
- The DNS sniffer actually capturing on the wire (needs `CAP_NET_RAW` on Linux;
  the parsers are unit-tested).
- `systemctl status mini-soc-ids` active with the `AmbientCapabilities` applied.

These need the live Ubuntu/EC2 host and should be ticked off in the next
deployment rehearsal (same outstanding class of items as the Phase 2/3 reports).

## 5. Sign-off

All Phase 4 tasks owned by M1/M2 are implemented and — for everything that runs
off-box — verified green: 21 IDS unit tests, the backend action-route tests, and
the 13-rule replay (now including `NET-OUTBOUND-001` and `DNS-ANOMALY-001`). The
remaining unknowns are Linux/EC2 runtime checks.

| Reviewer | Role | Sign-off | Date |
|---|---|---|---|
| M1 | IDS deployment / systemd / least privilege | Approved | 2026-10-14 |
| M2 | Requirements / detection / pipeline / tests | Approved | 2026-10-14 |
