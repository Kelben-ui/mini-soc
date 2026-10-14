# Phase 7 — M5 Sign-off Report

> **Status:** Implemented / verified / signed off
> **Date:** 2026-10-14
> **Baseline:** branch `main`, base commit `09924d2` (Phase 2 all-member fix), Phase 7
> code landed in `e68a6a3`, this report committed immediately after
> **Scope:** Phase 7 tasks 7.1–7.6 — frontend completion (spec §4.10) plus the small
> backend additions those tasks require (alert filters/pagination, linked events,
> alert promotion, and the dashboard statistics). All tasks owned by M5.
> **Method:** code inspection plus repeatable test runs (pytest, replay, frontend
> build/lint) and a real-HTTP smoke test of the new/modified endpoints against a
> running `uvicorn`.

---

## 1. Verification commands and results

| Check | Command | Result |
|---|---|---|
| Backend tests (incl. new alert/stat routes) | `pytest backend -q` | **21 passed** (was 14) |
| IDS tests | `pytest ids -q` | **21 passed** |
| Collector tests | `pytest collector -q` | **36 passed** |
| Log-agent tests | `pytest agents -q` | **15 passed, 1 skipped** (POSIX-only rotation test) |
| Combined | `pytest ids backend collector agents -q` | **93 passed, 1 skipped** |
| Import smoke (CI) | `python -c "import mini_soc_config, collector.main, detection.run, backend.app.main, agents.log_agent.agent, ids.config, ids.live_ids_ips, ids.dns_sniffer"` | **imports ok** |
| End-to-end detection | `python detection/tests/replay_test.py` | **REPLAY TEST PASSED** |
| Frontend build | `npm run build` | **built** — `dist/` produced, `dist/playbooks/*.md` copied |
| Frontend lint | `npm run lint` | **0 errors** (React-hooks/style warnings only) |
| HTTP smoke (new endpoints) | `uvicorn backend.app.main:app` + `requests` | **21/21 checks passed** (login, alert list envelope + filters, alert detail with linked events, `/users`, stats extras, promote, double-promote rejected, open-incident increment) |

The single skip is the POSIX-only log-rotation test (`agents`), unchanged from
Phase 4 (it needs `DATABASE_URL`/POSIX file rotation; skipped on Windows, runs in CI).

## 2. Task-by-task verification

| Task | Owner | Status | Evidence |
|---|---|---|---|
| 7.1 Quick fixes | M5 | Pass | All `console.error` calls removed from the dashboard (`EventSearch`, `IncidentsList`, `IncidentDetail`, `Rules`) and replaced with in-UI error state. `FALSE POSITIVE` present in the alert status filters and the status dialog (reason required, validated backend-side). `CONTAINED` present in the same lists. Event search now sends `src_ip`, `host`, `log_type`, `start_time`, `end_time` and renders real columns instead of the non-existent `source`/`payload`. `IncidentsList` row links fixed (added the missing `Link` import — was a runtime `ReferenceError`). A single `SeverityBanner` is rendered once in the app shell. |
| 7.2 Auth | M5 | Pass | `login()` decodes the JWT and persists `role`; `client.js` 401 interceptor clears `jwt`+`role` and redirects to `/login`; lead-only controls are hidden via `isLead()` (change status, assign, export evidence) while the backend remains the boundary (§16). |
| 7.3 Styling | M5 | Pass | Tailwind v4 (already wired through `@tailwindcss/postcss`) is applied across every page/component; `index.css` reduced to the Tailwind import plus a small dark base; the leftover Vite template `frontend/src/styles/app.css` (defining `.counter`/`.hero`, none of the SOC classes) was deleted. Responsive: mobile top bar + menu toggle switching to a `md:` sidebar, responsive tile/filter grids, and horizontally scrollable tables. |
| 7.4 Overview | M5 | Pass | `Overview.jsx` renders severity tiles, a 24-hour Recharts line chart, top source IPs, top attack types, open incidents, and the agent + IDS health panel, polling `/api/stats` every 10 s. Backed by the new `alerts_over_24h`, `top_source_ips`, `top_attack_types`, `open_incidents` keys (§15). |
| 7.5 Alerts list | M5 | Pass | `AlertsList.jsx` filters by severity, status, rule ID and source IP, paginates server-side (`limit`/`offset`), and refreshes every 8 s (< the 10 s requirement). Backed by the new `GET /api/alerts` filters/envelope (§13.4). |
| 7.6 Alert detail | M5 | Pass | `AlertDetail.jsx` renders all model fields (incl. `dst_host`, `mitre`, `category`), the linked raw events, a status dialog (comment required; reason required for FALSE POSITIVE), assignment, promotion, evidence export, and the mapped response playbook. Backed by linked events on `GET /api/alerts/{id}`, `PATCH /api/alerts/{id}`, `POST /api/alerts/{id}/export-evidence` and the new `POST /api/alerts/{id}/promote`. |

### Backend support added for 7.4–7.6

| Endpoint | Change |
|---|---|
| `GET /api/alerts` | Now accepts `severity`, `status`, `rule`/`rule_id`, `src_ip`, `assigned_to`, `start_time`, `end_time`, `limit`, `offset` and returns `{items, total, limit, offset}` (§13.4). |
| `GET /api/alerts/{id}` | Now includes the linked `events` (raw log line plus normalized fields) (§13.4). |
| `POST /api/alerts/{id}/promote` | Creates an incident from the alert, links `alert.incident_id`, and writes an audit entry (§5.1 / §14.1). |
| `GET /api/stats` | Adds `alerts_over_24h`, `top_source_ips`, `top_attack_types`, `open_incidents` (§15). |

New tests: `backend/tests/test_alerts_route.py` (7 tests) covers the pagination
envelope, severity/status/IP/time filters, linked events on detail, promotion and
its audit entry, double-promotion rejection, and the new statistics keys.

### Browser-side evidence (supporting §2)

| Check | Method | Result |
|---|---|---|
| New/modified API contract over real HTTP | `uvicorn` + `requests` script (login → list → detail → stats → promote → re-promote) | **21/21 checks passed** |
| Production bundle builds and copies static assets | `npm run build` | **ok** — `dist/index.html`, hashed JS/CSS, `dist/playbooks/*.md` |

## 3. Notes and deviations

1. **`GET /api/alerts` response shape changed.** It previously returned a bare
   list; pagination requires an envelope, so it now returns
   `{items, total, limit, offset}`. The only two callers (the shell severity
   banner and the alerts page) were updated in the same change.
2. **Promotion endpoint.** Promotion is exposed as `POST /api/alerts/{id}/promote`
   (analyst/lead/admin) rather than the frontend calling `POST /api/incidents`
   directly, so that creating the incident, linking the alert and writing the
   audit entry happen in one transaction and the incident↔alert link required by
   §13.4/§14.2 is guaranteed. `POST /api/incidents` remains the general
   incident-create endpoint (§14.1) and is unchanged.
3. **Case-insensitive filters.** Alert `severity`/`status` filters compare
   case-insensitively (`upper(...)`) so the dashboard does not have to match the
   engine's stored casing exactly.
4. **`open_incidents`** counts incidents whose status is `open`, `investigating`
   or `contained` (i.e. not yet resolved/closed).
5. **Playbooks.** The alert detail playbook panel fetches the existing
   `frontend/public/playbooks/*.md` files via the `PLAYBOOK_MAP` rule→file map;
   Vite copies them into `dist/` and nginx serves them through the SPA fallback.
6. **Role gating is UX, not security.** Hiding lead-only controls in the browser
   is a convenience; the backend remains the authorisation boundary (§16), and
   the new promote endpoint enforces its own role check.
7. **Bundle size.** Recharts raises the minified JS bundle to ~705 kB, so Vite
   prints its >500 kB advisory. This is a warning, not a build failure; code
   splitting can be added later if needed.

## 4. Not verifiable from this machine

- Visual rendering and responsive behaviour at real viewport widths (desktop,
  tablet, phone) — needs a browser.
- The 10 s / 8 s live polling as observed in a running browser. The polling
  intervals are in the code and the polled endpoints were exercised over HTTP;
  the visual refresh cadence needs a browser session.
- nginx serving the built `frontend/dist` (including `/playbooks`) and proxying
  `/api` on the target host.
- Recharts chart interactivity (tooltip/hover) in a browser.

These are the same outstanding class of environment-dependent items noted in the
Phase 2–4 reports and should be ticked off during the deployment rehearsal.

## 5. Sign-off

All Phase 7 tasks (7.1–7.6) owned by M5 are implemented and verified green for
everything that runs off-box: 21 backend tests (7 new), the full combined suite
(93 passed, 1 skipped), the 13-rule detection replay, a clean frontend
build/lint, and a 21-check real-HTTP smoke test of the new endpoints.

| Reviewer | Role | Sign-off | Date |
|---|---|---|---|
| M5 | Frontend / dashboard | Approved | 2026-10-14 |
