# Phase 1 — M1/M2 Sign-off Report

> **Status:** Verified / signed off
> **Date:** 2026-10-13
> **Baseline:** branch `main`, HEAD `a8b7607` (Phase 1 landed in `431f9e6`), clean working tree
> **Scope:** Phase 1 tasks owned by M1 and M2 — 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.8
> **Method:** code inspection plus repeatable test runs. Verification only — no source
> changes were made to produce this report.

---

## 1. Verification commands and results

| Check | Command | Result |
|---|---|---|
| Collector unit tests | `pytest collector/tests -v` | **31 passed** (2 FastAPI `on_event` deprecation warnings) |
| End-to-end detection | `DATABASE_URL=sqlite:///./ci-replay.db PYTHONPATH=. python detection/tests/replay_test.py` | **REPLAY TEST PASSED** — 13/13 rules fired |
| Sample-data parse | every line in `sample-data/` through its parser | **0 unparsed** — 326 + 3 + 16 + 4 + 3 lines |
| Rule contract fields | `id` / `category` / `mitre` present in `rules/*.yaml` | **13 rules**, each with `category:` and `mitre:` |

The replay run creates `ci-replay.db` as a throwaway artifact (the same file CI uses);
it was removed afterwards and is not part of the change set.

## 2. Task-by-task verdict

| # | Owner | Verdict | Evidence |
|---|---|---|---|
| 1.1 | M2–M5 | Pass (with assumption) | `docs/contracts.md` frozen v1.0 (2026-10-11): event model (§2.2–2.4), log source conventions (§2.5), IDS JSON output format (§2.6), alert model (§3), incident model (§5), API contract (§13–16). Freeze record in §23 carries the M3/M4 approvals. The literal "signed off in the PR" is not verifiable from the repository alone. |
| 1.2 | M1 + M2 | Pass | `deploy/nginx/mini-soc.conf` defines `log_format soc escape=none '... body=$request_body'` and `access_log /var/log/nginx/access.log soc;`. `collector/parsers/nginx_access_parser.py` emits `action=http_request`, `details.{method,uri,query,status,bytes,user_agent,body}` and applies `unquote_plus` twice to `uri`/`query`/`body`. Test asserts `%27+OR+1%3D1` → `id=' OR 1=1`. |
| 1.3 | M2 | Pass | `collector/parsers/suricata_parser.py` (log type `mini_soc_ids`): generic alert → `ids`/`ids_alert`; signature 9000001 → `network`/`port_scan`; `dns`/`dns_query` → `dns`/`unusual_dns`; `outbound`/`outbound_connection` → `network`/`unusual_outbound`. `details.{signature_id,signature,priority,count}` and the real host are set. Tests use real IDS lines. |
| 1.4 | M2 | Pass | `collector/parsers/firewall_parser.py` parses journald/kern `SOC_DROP:`/`SOC_ACCEPT:`/`SOC_OUT:` lines with `SRC/DST/SPT/DPT/PROTO` (`drop`/`accept`/`out`), including `-o cat` lines without a timestamp. Tests use real EC2 kern lines. |
| 1.5 | M2 | Pass | `collector/parsers/common.py`: `get_hostname()` (`SOC_HOSTNAME` → `socket.gethostname()`), `get_private_ip()` (`SOC_PRIVATE_IP` → auto-detect), `to_utc_iso()` (UTC `...Z`). Wired into every parser. |
| 1.6 | M2 + M6 | Pass (with caveat) | At least 3 valid lines plus malformed cases per parser type; `sample-data/` covers all 13 rules and every line parses. Caveat: the sample logs are hand-built to be byte-format-identical, not captured from the EC2 host (see §3). |
| 1.8 | M2 | Pass | `collector/main.py` returns `503` when the backend is unreachable, times out, or returns 5xx; the log agent spools and replays once the collector is reachable. Covered by `collector/tests/test_collector_ingest.py`. |

Task 1.7 (align the 13 rule YAMLs, add `category:` and `mitre:`) is M3-owned and out of
scope, but is confirmed done: all 13 rules carry both fields.

## 3. Open items and deviations

1. **1.6 — real lab capture outstanding.** `sample-data/README.md` records that the EC2
   box was unreachable, so the logs are hand-built. The literal "lab logs from the EC2
   host" is unmet until the box is reachable; `sample-data/generate.py` and the README
   describe the replacement procedure.
2. **1.3 — wording vs frozen contract.** The task text names actions
   `dns_query`/`outbound_connection`, whereas the implementation uses
   `unusual_dns`/`unusual_outbound`. This matches the frozen contract (§2.6) and the rule
   YAMLs, so it is treated as imprecise task wording, not a defect.
3. **1.1 — "signed off in the PR"** cannot be verified from the repository; the in-document
   freeze record (§23) stands in for it.
4. **Minor:** `collector/main.py` uses the deprecated `@app.on_event("startup")` hook
   (FastAPI lifespan is preferred). Non-blocking.

## 4. Sign-off

All Phase 1 tasks owned by M1 and M2 are implemented, tested, and green at HEAD
`a8b7607`. The log pipeline is unbroken end-to-end. The only substantive gap is the
provenance of the 1.6 sample data, which depends on EC2 availability.

| Reviewer | Role | Sign-off | Date |
|---|---|---|---|
| M1 | nginx config | Approved | 2026-10-13 |
| M2 | Collector / pipeline | Approved | 2026-10-13 |
