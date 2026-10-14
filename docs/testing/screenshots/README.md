# Dashboard screenshot tooling

Generates every image used by [`docs/user-guide.md`](../../user-guide.md).

Two steps: **seed** a throwaway database with demo data, then **capture** the
running dashboard with a headless browser. The output PNGs are committed to
`docs/images/screenshots/`, so the guide renders on GitHub without a live stack.

This folder is a standalone helper — it is **not** part of the application build,
the CI pipeline, or the deployed stack.

## 1. Seed demo data

```powershell
# from the repo root, with the project venv active
python docs/testing/screenshots/seed_demo.py
```

It creates `demo-screenshots.db` (SQLite, git-ignored) containing:

* three users — `analyst`, `lead`, `admin`, password `demo-password-123`;
* one event set per detection rule, then runs the **real** detection engine so
  the alerts, chain links and dedupe behaviour are genuine (13/13 rules fire);
* one incident (`INC-2026-0001`) with notes, response actions and status history.

All timestamps are relative to "now" and stay inside the engine's widest rule
window (300 s), so the data is always "fresh". Re-running is safe: it first
deletes the demo source(s) and incident it previously created. Override the
location with `DATABASE_URL`.

## 2. Start the stack against the demo database

Two processes. Backend (set `EVIDENCE_DIR`/`VAR_DIR` on Windows — the defaults are
POSIX paths):

```powershell
$env:DATABASE_URL        = "sqlite:///./docs/testing/screenshots/demo-screenshots.db"
$env:EVIDENCE_DIR        = "$env:TEMP\mini-soc-evidence"
$env:VAR_DIR             = "$env:TEMP\mini-soc-var"
$env:INGEST_API_KEY      = "demo-key"
$env:JWT_SECRET_KEY      = "demo-secret"
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8000
```

Dashboard. `npm run dev` is the normal path; a production preview works too and
is lighter (it reuses the same `/api` proxy — see `frontend/vite.config.js`):

```powershell
cd frontend
npm run build
npm run preview        # serves http://127.0.0.1:4173
```

## 3. Capture

```powershell
cd docs/testing/screenshots
npm install            # the playwright package (browsers are optional, see below)
node capture.mjs
```

`capture.mjs` logs in through the real form, then visits each route and writes
`00-login.png` … `11-users.png` into `docs/images/screenshots/`. Detail pages
(`/alerts/:id`, `/chains/:id`, `/incidents/:id`) are discovered through the
authenticated API, so the IDs always match the seeded data. A route that fails to
render is logged and skipped rather than aborting the run.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `MINI_SOC_URL` | `http://127.0.0.1:5173` | Dashboard origin to capture |
| `MINI_SOC_USER` | `admin` | Login username |
| `MINI_SOC_PASS` | `demo-password-123` | Login password |
| `MINI_SOC_SHOTS` | `docs/images/screenshots` | Output directory |
| `MINI_SOC_CHANNEL` | (auto) | Force a browser channel, e.g. `chrome` / `msedge` |

### Browsers

The script prefers a Playwright-managed Chromium, but falls back to an installed
Chrome or Edge (`channel: 'chrome'` / `'msedge'`) — useful when
`npx playwright install` cannot run. To install the bundled browser instead:

```powershell
npx playwright install chromium
```

`PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` skips the download during `npm install`.

## Refresh checklist

When the UI changes, re-run steps 1–3 and commit the changed PNGs together with
the change that moved them. Keep filenames in sync with the references in
`docs/user-guide.md`.
