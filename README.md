# Mini SOC Platform

A security monitoring and incident response platform for collecting logs,
normalizing events, detecting suspicious activity, and investigating alerts.

## Project structure

- `agents/` — log collection agents and service templates.
- `collector/` — receives and parses log entries.
- `detection/` — detection engine.
- `rules/` — detection rules.
- `backend/` — FastAPI application, database models, and migrations.
- `frontend/` — React and Vite interface.
- `infrastructure/` — lab and firewall configuration.
- `attack-sim/` — authorized lab simulations.
- `playbooks/` — incident response procedures.
- `sample-data/` — sample events and test data.
- `docs/` — project documentation and testing notes.

## Event pipeline

Log files → Log agent → Collector → Backend API → PostgreSQL.

The custom Mini SOC IDS writes JSON alerts to
`/var/log/mini_soc_ids.json`.

## Requirements

- Python and the required packages for each component.
- PostgreSQL configured for the backend.
- Node.js and npm for the frontend.
- A configured root `.env` file.

Never commit `.env` or real credentials.

## Start the backend

From the repository root:

    cd backend
    ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

API root: http://127.0.0.1:8000/
API documentation: http://127.0.0.1:8000/docs

## Start the frontend

    cd frontend
    npm run dev

Use the local URL printed by Vite.

## Database migrations

Alembic configuration is `backend/alembic.ini`.
Migration files are under `backend/migrations/versions/`.

## Security

Restrict access to authorized users and systems. Use strong secrets, keep
`.env` private, and review development settings before deployment.

See `docs/` for architecture, API contracts, rules, lab setup, and testing.
