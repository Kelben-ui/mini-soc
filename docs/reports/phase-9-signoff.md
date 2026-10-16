# Phase 9 — Live testing, security review & deliverables — Sign-off Report

> **Status:** Off-box deliverables complete; live-host rows pending operator run
> **Date:** 2026-10-16
> **Baseline:** branch `main`, head `5bab672` (pushed to `origin`).
> **Scope:** Phase 9 tasks 9.1–9.8 — the results matrix, the platform security
> review, the response playbooks, the demo script, the incident reports, the
> READMEs and analyst guide, CI, and the slide deck.
> **Method:** everything that runs off-box is executed here (pytest across all
> Python components, the 13-rule detection replay, the frontend suites, the
> screenshot capture and the slide build). The live attack-simulation matrix,
> the EC2 exposed-ports scan and the demo rehearsals need the running instance
> and the Kali attacker VM; they are recorded as **pending** and driven by
> [`docs/testing/live-runbook.md`](../testing/live-runbook.md).

---

## 1. Verification commands and results

| Check | Command | Result |
|---|---|---|
| Full Python suite | `pytest -q` | **131 passed, 1 skipped** |
| Detection replay (13 rules vs SQLite) | `python detection/tests/replay_test.py` | **PASSED** — 13/13 rules, 341 alert↔event links |
| Backend security tests (9.2) | `pytest backend/tests/test_security.py` | **11/11 pass** |
| Frontend unit/component tests | `npm test` | **18 passed** (5 files) |
| Frontend production build | `npm run build` | **ok** |
| Frontend lint | `npm run lint` | **0 errors** (pre-existing warnings only) |
| Dashboard screenshots | `node docs/testing/screenshots/capture.mjs` | **12/12 captured** |
| Slide deck build | `python docs/slides/build_slides.py` | **16 slides**, round-trips in python-pptx |

The one skipped test is the POSIX-only log-agent rotation test carried over from
Phase 3/4; unrelated to this change.

## 2. Task-by-task

| Task | Status | Evidence |
|---|---|---|
| 9.1 Results matrix (all attack-sim scripts, expected vs actual, detection time, false positives) | **Pending live** | Scaffold in `docs/testing/results.md`: the 13-row matrix with expected severities, plus the dedupe, correlation and block/unblock rows. Commands in `docs/testing/live-runbook.md`. Target 13/13. |
| 9.2 Platform security test (SQLi, XSS, IDOR, JWT tampering, upload abuse, EC2 ports, IPS helper injection) | **Done (off-box) / ports scan pending** | `backend/tests/test_security.py` (11/11) covers SQLi/XSS, IDOR/RBAC, JWT tampering, upload abuse and helper injection. `docs/testing/security-test.md`. The EC2 `nmap` exposed-ports scan needs the live host. **No open High findings.** |
| 9.3 Playbooks | **Done** | One merged, placeholder-free `playbooks/incident-response.md` covering all 13 rules; `playbooks/README.md`. The dashboard maps every rule id to it (`frontend/src/playbookMap.js`), and `frontend/scripts/sync-playbooks.mjs` copies the single canonical file into the build on `predev`/`prebuild` (one copy). |
| 9.4 Demo script + 2 rehearsals | **Done (script) / rehearsals pending** | `docs/demo-script.md` adapted to the single-EC2 lab; rehearsal-log table present. The two timed rehearsals need the live lab. |
| 9.5 Incident reports | **Done** | `docs/reports/incident-reports.md` — `INC-2026-0001` (confirmed multi-stage intrusion, 13 alerts → 1 chain → block) and `INC-2026-0002` (benign second source, false positive). |
| 9.6 Folder READMEs + analyst guide | **Done** | New `agents/`, `collector/`, `rules/`, `infrastructure/`, `deploy/`, `docs/` READMEs; rewritten `docs/user-guide.md` with 12 screenshots in `docs/images/screenshots/` captured by the tooling in `docs/testing/screenshots/`. |
| 9.7 GitHub Actions (pytest + `npm test` + `npm run build`) | **Done** | `.github/workflows/ci.yml`: combined pytest, detection replay, a shell-syntax loop over `deploy/` + `attack-sim/`, and a frontend job (`npm ci` + test + build), with caching, a concurrency group and `permissions: contents: read`. |
| 9.8 Slides | **Done** | `docs/slides/mini-soc-overview.pptx` (16 slides) plus the reproducible generator `docs/slides/build_slides.py`. |

## 3. Verified off-box vs. needs the live host

**Verified here (this machine):** the entire Python suite, the 13-rule replay,
the frontend test/build/lint, the app-level security checks, the screenshot
pipeline and the slide build. These are enough to state that detection,
correlation, the API, the dashboard and the security controls behave as
specified against the sample/replay dataset and the automated security tests.

**Needs the live EC2 host + Kali attacker VM:**

1. **9.1** — running the attack-sim scripts and recording expected vs actual,
   detection time and false positives in `docs/testing/results.md`.
2. **9.2** — the `nmap` exposed-ports scan of the instance (expect only 22/80,
   plus 443 for the analyst IP) and the on-host `ss -tlnp` cross-check.
3. **9.4** — the two timed demo rehearsals.

Host-originated rules (#12 outbound, #13 DNS) run *on the instance*; the
nmap/hydra items run from Kali. The full command set is in
[`docs/testing/live-runbook.md`](../testing/live-runbook.md).

## 4. Notes and decisions

1. **One playbook, one copy.** The three per-attack playbooks were merged into
   `playbooks/incident-response.md`; the dashboard's playbook view resolves every
   rule id to it, and a build-time sync keeps a single source of truth (the
   `frontend/public/playbooks/` copy is generated and git-ignored).
2. **Off-box security coverage is automated.** Rather than only narrate the
   security review, `backend/tests/test_security.py` asserts the controls
   (parameterized filters, authz/IDOR, JWT expiry, evidence outside the webroot,
   the 8-char password floor, and `soc-block` IPv4/allow-list/injection
   resistance) so regressions are caught in CI.
3. **Screenshot pipeline.** The `npm run dev` optimizer needed more memory than
   the build machine had and the bundled-Chromium download hit a full disk, so
   the capture runs against a production `vite preview` (with an `/api` proxy
   mirroring dev) and falls back to the installed Chrome/Edge channel. See
   `docs/testing/screenshots/README.md`.
4. **Follow-up fixes folded in before sign-off** (all with tests where the change
   was testable): the Postgres role bootstrap uses `gexec` instead of a `DO`
   block; an Alembic migration adds the alert `dst_host`/`mitre`/`category`
   columns; the collector parses rsyslog ISO auth lines and RFC3339 journal
   offsets and accepts empty nginx request fields for anonymous requests; the
   nginx `soc` format logs `:80`; and the user password floor was lowered to 8
   across the schema, CLI and dashboard to match the policy.
5. **CI is the gate.** The workflow fails on any pytest failure, a broken
   replay, a shell syntax error in the deploy/attack scripts, or a failing
   frontend test/build.

## 5. Sign-off

All Phase 9 work that can be executed off-box is complete and green (131 Python
tests pass, the 13-rule replay passes, the 11/11 security tests pass, and the
frontend test/build/lint are clean). The remaining rows — the live 13-rule
matrix (9.1), the EC2 exposed-ports scan (9.2), and the two demo rehearsals (9.4)
— require the running instance and the Kali VM and are to be completed by the
operator per `docs/testing/live-runbook.md`, then recorded in
`docs/testing/results.md` and `docs/testing/security-test.md`.

| Reviewer | Role | Sign-off | Date |
|---|---|---|---|
| Team | Off-box deliverables (9.2 offline, 9.3–9.8) | Approved | 2026-10-16 |
| Operator | Live EC2 matrix, ports scan, rehearsals (9.1, 9.2, 9.4) | Pending | |
