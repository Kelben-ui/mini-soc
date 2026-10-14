# Phase 7 (continued) — M5 Sign-off Report

> **Status:** Implemented / verified / signed off
> **Date:** 2026-10-14
> **Baseline:** branch `main`, previous head `2431bd2` (Phase 7 §7.1–7.6 report).
> The continuation code landed in `e90b3c5`; this report is committed immediately
> after.
> **Scope:** Phase 7 tasks 7.7–7.11 — attack-chain review and promotion, the full
> incident-response workspace, the event/rule/user/report screens, the live threat
> level banner, and the frontend test harness. All tasks owned by M5.
> **Method:** code inspection plus repeatable test runs (pytest, detection replay,
> frontend build/lint/test) and a real-HTTP smoke test of the new/modified
> endpoints against a running `uvicorn`.

---

## 1. Verification commands and results

| Check | Command | Result |
|---|---|---|
| Backend tests (incl. new chains/incident/users/rules/stats routes) | `pytest backend -q` | **44 passed** (was 21; +23) |
| Combined | `pytest ids backend collector agents -q` | **116 passed, 1 skipped** |
| Detection replay (13 rules vs SQLite) | `python detection/tests/replay_test.py` | **PASSED** — 341 alert↔event links |
| Frontend unit/component tests | `npm test` (`vitest run`) | **18 passed** (5 files) |
| Frontend production build | `npm run build` | **ok** — `dist/index.html`, hashed JS/CSS, `dist/playbooks/*.md` |
| Frontend lint | `npm run lint` (`oxlint`) | **0 errors** (warnings only — see §3.9) |
| New/modified API contract over real HTTP | `uvicorn` + `requests` script | **43/43 checks passed** |

The one skipped test is the POSIX-only log-agent rotation test carried over from
Phase 3/4; it is unrelated to this change. The 44 backend tests include 23 new
ones added for 7.7–7.10 (`test_chains_route.py`, `test_incident_detail.py`,
`test_users_route.py`, `test_rules_stats.py`).

## 2. Task-by-task

| Task | Owner | Result | Evidence |
|---|---|---|---|
| 7.7 Attack-chain review | M5 | Pass | New `backend/app/routers/chains.py` groups alerts sharing a `chain_id` (§4.2/§4.3) and exposes `GET /api/chains` (`only_unpromoted`/`since` filters, `{items,total}`, newest first) and `GET /api/chains/{id}` (summary + alerts in first-seen order). Frontend `ChainsList.jsx` lists chains with severity/IP/host/category columns; `ChainDetail.jsx` renders the correlated activity as a kill-chain timeline grouped by ATT&CK tactic via `constants/mitre.js` (`tacticForTechnique`, `groupAlertsByTactic`). |
| 7.7 Promotion | M5 | Pass | `POST /api/chains/{id}/promote` creates one incident, links every alert in the chain, and writes the audit entry in a single transaction (atomic). Returns the new `incident_code`/`alert_count`; a second call returns **409**. |
| 7.8 Incident detail | M5 | Pass | `GET /api/incidents/{id}` now returns `contained_at`/`resolved_at`, `alert_count`, `alert_ids`, and detection-anchored `ttd_seconds`/`ttc_seconds`/`ttr_seconds`. `IncidentDetail.jsx` is rebuilt around the response timeline, alert list, notes, evidence, response actions and the report. |
| 7.8 Notes / evidence / timeline | M5 | Pass | `GET/POST /api/incidents/{id}/notes`, `GET /api/incidents/{id}/evidence`, `GET /api/evidence/{id}/custody`, `GET /api/evidence/{id}/download` (authenticated), and `GET /api/incidents/{id}/timeline` (merged note/evidence/custody/action/status history). |
| 7.8 Editing & status | M5 | Pass | `PATCH /api/incidents/{id}` edits description/category/root_cause/lessons_learned (analyst+) and re-assignment (lead/admin only), each audited. Status changes stamp `contained_at` and `resolved_at`; a new Alembic migration (`c3d4e5f6a7b8`) adds those columns. |
| 7.9 Event search pagination | M5 | Pass | `GET /api/events` now accepts `limit` (1–500) / `offset` and returns `{items,total,limit,offset}`. `EventSearch.jsx` pages the results and shows "showing X–Y of N". |
| 7.9 Rule inventory | M5 | Pass | `GET /api/rules` is rewritten to read the YAML rule files and enrich each with live `alerts_count` and `last_fired` (from alerts), returning normalised `id/name/severity/category/enabled/mitre`. `Rules.jsx` shows technique, tactic, fire count and last-fired. |
| 7.9 Reports page | M5 | Pass | New `Reports.jsx` (task spec §4): totals, threat level, MTTA-style tiles (MTTD/MTTC/MTTR), alerts-by-severity, and an incident-report table that downloads the generated HTML report through the authenticated blob API. |
| 7.9 User management | M5 | Pass | New `backend/app/routers/users.py`: `GET/POST /api/users`, `PATCH /api/users/{id}`, `POST /api/users/{id}/password` (lead for read, admin for writes), all audited. Guardrails: unique usernames, valid roles only, last admin cannot be demoted, self role-change blocked, 8-char password minimum. New `Users.jsx` provides create / change-role / reset-password. |
| 7.10 Threat level | M5 | Pass | `GET /api/stats` computes a server-side `threat_level` (highest of the active-alert and open-incident severities) plus `active_alerts`, `active_alerts_by_severity` and `mean_time_to_detect/contain/resolve_seconds`. `SeverityBanner.jsx` is rewritten to poll `/api/stats` and show the shared posture (level + active alerts + open incidents, with an "Investigate" link when HIGH/CRITICAL). |
| 7.11 Frontend tests | M5 | Pass | Vitest + React Testing Library (jsdom). `npm test` runs 18 tests across 5 files: `utils/format`, `constants/mitre`, and component/page tests for `SeverityBanner`, `Rules` and the `ChainsList` promote flow. `src/test/setup.js` registers the jest-dom matchers. |
| 7.11 CI & docs | M5 | Pass | `.github/workflows/ci.yml` adds a frontend `npm test` step after the build. `frontend/README.md` is rewritten (requirements, dev proxy, build, test, lint, deployment/nginx, layout, config table). |

### New/changed API surface

| Endpoint | Change |
|---|---|
| `GET /api/chains` | New. Correlated chains, `only_unpromoted`/`since`, `{items,total}`. |
| `GET /api/chains/{id}` | New. Chain summary + ordered alerts. |
| `POST /api/chains/{id}/promote` | New. Atomic promotion; 409 if already promoted. |
| `GET /api/incidents/{id}` | Enriched with response timestamps, `alert_count`, `ttd/ttc/ttr_seconds`. |
| `PATCH /api/incidents/{id}` | New. Edit narrative fields / assignee (audited). |
| `GET /api/incidents/{id}/notes` · `POST …/notes` | Existing list + new create. |
| `GET /api/incidents/{id}/evidence` | New. List evidence for an incident. |
| `GET /api/evidence/{id}/custody` | New. Chain-of-custody entries. |
| `GET /api/incidents/{id}/timeline` | New. Merged investigation timeline. |
| `GET /api/events` | Now `limit`/`offset` + `{items,total,limit,offset}` envelope. |
| `GET /api/rules` | Enriched with `alerts_count`/`last_fired` and normalised fields. |
| `GET /api/users` · `POST /api/users` · `PATCH /api/users/{id}` · `POST /api/users/{id}/password` | New. Admin-only management with guardrails and audit. |
| `GET /api/stats` | Adds `threat_level`, `active_alerts`, `active_alerts_by_severity`, `mean_time_to_*_seconds`. |

## 3. Notes and deviations

1. **`GET /api/events` response shape changed.** It previously returned a bare
   list; pagination requires an envelope, so it now returns
   `{items,total,limit,offset}` (default `limit=100`, max 500). The only caller
   (`EventSearch.jsx`) was updated in the same change.
2. **Chains are derived, not stored.** Chains are the set of alerts sharing a
   `chain_id` stamped by the detection engine (§4.2); no new table is introduced.
   `promoted` is true once any alert in the chain has an `incident_id`.
3. **Promotion is atomic and idempotent-safe.** Incident creation, alert linking
   and the audit entry share one commit. Re-promoting returns 409 rather than
   creating a duplicate incident (§4.3/§19).
4. **Response metrics are detection-anchored.** TTD = incident `created_at` minus
   the earliest linked alert `first_seen`; TTC = `contained_at − created_at`;
   TTR = (`resolved_at` or `closed_at`) − `created_at`. Any missing timestamp
   yields `null`, which the UI renders as an em dash.
5. **New migration.** `c3d4e5f6a7b8_add_incident_response_timestamps.py`
   (`down_revision = "b2c3d4e5f6a7"`) adds `incidents.contained_at` and
   `incidents.resolved_at`. Status transitions populate them.
6. **Threat level is server-side.** It is the highest severity among alerts that
   are not resolved/false-positive/closed and incidents still
   open/investigating/contained, so every client agrees on the posture rather than
   re-deriving it in the browser.
7. **User-management guardrails.** Beyond the 8-character minimum, the API
   rejects duplicate usernames (409), invalid roles (400), demoting the last
   admin, and changing your own role (both 400). The legacy
   `GET /users` shim in `main.py` is retained for backward compatibility while the
   dashboard now uses `/api/users`.
8. **Evidence storage path fix.** Evidence upload previously built its storage
   directory from the process CWD; it now uses
   `mini_soc_config.evidence_dir()` (`EVIDENCE_DIR`), matching the rest of the
   platform.
9. **Local lint warnings.** `oxlint` reports zero errors; the remaining messages
   are the pre-existing `react(set-state-in-effect)` and
   `react-hooks(exhaustive-deps)` advisories, consistent with the rest of the
   codebase.
10. **Vitest/Vite JSX runtime.** Vitest 3 bundles its own Vite 7 copy while the
    project builds with Vite 8, so JSX in test files compiled with the classic
    runtime. `vite.config.js` now pins `esbuild.jsx: "automatic"` so tests and the
    production build agree.
11. **Role gating is UX, not security.** Hiding lead/admin controls in the browser
    is a convenience; the backend remains the authorisation boundary (§16) and
    every new endpoint enforces its own role check.

## 4. Not verifiable from this machine

- Visual rendering and responsive behaviour of the new pages (Chains, Reports,
  Users, rebuilt IncidentDetail) at real viewport widths — needs a browser.
- Live polling cadence in a running browser (threat banner 10 s, reports 15 s).
  The intervals are in the code and the polled endpoints were exercised over HTTP.
- nginx serving the built `frontend/dist` (including `/playbooks`) and proxying
  `/api` on the target host.
- Real IPS execution of a block/unblock action (the confirmation flow is in the
  UI; executing requires the host IPS helper, so the smoke test only records the
  action).

These are the same outstanding environment-dependent items noted in the
Phase 2–4 and 7.1–7.6 reports and should be ticked off during the deployment
rehearsal.

## 5. Sign-off

All Phase 7 tasks 7.7–7.11 owned by M5 are implemented and verified green for
everything that runs off-box: 44 backend tests (23 new), the full combined suite
(116 passed, 1 skipped), the 13-rule detection replay, a clean frontend
build/lint and an 18-test frontend suite, plus a 43-check real-HTTP smoke test of
the new endpoints.

| Reviewer | Role | Sign-off | Date |
|---|---|---|---|
| M5 | Frontend / dashboard | Approved | 2026-10-14 |
