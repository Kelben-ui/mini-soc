# Mini SOC — Frontend

React 19 + Vite single-page dashboard for the Mini SOC platform. It talks to
the FastAPI backend under `/api` on the same origin in every environment, so no
CORS configuration or build-time API URL is required.

## Requirements

- Node.js 20+ and npm
- The backend running on `http://127.0.0.1:8000` for local development

## Install

```bash
cd frontend
npm ci
```

## Local development

```bash
npm run dev
```

Vite serves the dashboard on `http://127.0.0.1:5173` and proxies `/api/*` to
`http://127.0.0.1:8000` (see `vite.config.js`), mirroring nginx in production.
Start the backend separately, for example:

```bash
# from the repository root, with the project venv active
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

## Build

```bash
npm run build
```

The production bundle is written to `frontend/dist/` (hashed JS/CSS plus the
static `playbooks/*.md` files copied from `public/`). `npm run preview` serves
the built bundle locally.

## Test

```bash
npm test          # one-shot run (used by CI)
npm run test:watch
```

Vitest + React Testing Library run in a jsdom environment. The suite covers the
pure helpers (`utils/format`, `utils/severity`, `constants/mitre`) and key
components/pages (threat-level banner, Rules page, attack-chain promote flow).
`src/test/setup.js` registers the `@testing-library/jest-dom` matchers.

> The test-runner bundles its own Vite copy, which may compile JSX with the
> classic runtime. `vite.config.js` pins `esbuild.jsx: "automatic"` so tests and
> the production build agree.

## Lint

```bash
npm run lint
```

## Deployment

Production is served by nginx from `frontend/dist`; the deploy scripts build it
for you:

- `deploy/install.sh` and `deploy/update.sh` run `npm ci && npm run build` and
  relax permissions on `dist/`.
- `deploy/nginx/mini-soc.conf` sets `root <app>/frontend/dist`, serves the SPA
  with a `try_files ... /index.html` fallback, and proxies `location /api/` to
  `http://127.0.0.1:8000` **without** a trailing slash so the `/api` prefix is
  preserved.

`frontend/public/playbooks/*.md` are copied into `dist/playbooks/` at build
time and opened from alert details.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | *(empty)* | Only set this when the API lives on a different origin. Empty means same-origin `/api`, which works through both the Vite dev proxy and nginx. |

## Layout

```
src/
  api/            thin axios wrappers (auth, alerts, incidents, chains, rules, stats, users)
  components/     NavBar, ProtectedRoute, SeverityBanner
  constants/      ATT&CK technique -> tactic map (kill-chain timeline)
  pages/          Overview, AlertsList/AlertDetail, IncidentsList/IncidentDetail,
                  ChainsList/ChainDetail, EventSearch, Rules, Reports, Users, Login
  utils/          duration/byte/date formatting, severity + status styling
  test/           Vitest setup
```

Authentication is a JWT in `localStorage`; the axios client attaches it as a
`Bearer` token. Role-gated controls (incident status, response actions, user
management) are UX only — the backend enforces authorization.
