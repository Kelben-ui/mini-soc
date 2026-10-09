# Mini SOC Architecture

## Purpose

Mini SOC collects security events, detects suspicious activity, and supports
alert investigation and incident response.

## Components

### Log sources

Lab services generate logs. The custom Mini SOC IDS writes JSON alerts to
`/var/log/mini_soc_ids.json`.

### Log agent

`agents/log_agent/agent.py` watches nginx access logs, authentication logs,
and Mini SOC IDS JSON alerts. It forwards newly appended lines to the collector.
The current implementation starts reading at the end of each file.

### Collector

The FastAPI collector receives raw log entries, chooses a parser based on log
type, normalizes events, and forwards them to the backend ingestion endpoint.

### Backend

`backend/app/main.py` creates the FastAPI application and registers routers
for authentication, ingestion, events, alerts, incidents, rules, and statistics.

### Database

PostgreSQL stores application data. SQLAlchemy models are in
`backend/app/models/`. Alembic is configured by `backend/alembic.ini`, with
migration files under `backend/migrations/versions/`.

### Frontend

The React and Vite application is in `frontend/`.

### Detection and response

The detection engine evaluates normalized events against configured rules.
Alerts can be investigated and associated with incidents. Actual detection
coverage depends on the rules and engine currently implemented and running.

## Event flow

1. A service writes a log entry.
2. The agent forwards a new line to the collector.
3. The collector parses and normalizes the entry.
4. The collector forwards the event to the backend.
5. The backend validates and stores accepted events.
6. Detection logic evaluates events and may create alerts.
7. Analysts investigate alerts and manage incidents through the API and UI.

## Current service addresses

- Backend: `127.0.0.1:8000`
- Collector: `127.0.0.1:9000`

These addresses support communication within the EC2 instance.

## Configuration and operations

The backend loads `DATABASE_URL` from the repository-root `.env` file.
The collector uses `INGEST_API_KEY` when forwarding events.

The current collector and log agent have been running from
`/home/ubuntu/infrastructure`. Copying files into this repository does not
automatically change the running processes. Verify services before migrating
or removing the old directory.

Keep secrets out of Git and apply least-privilege access controls.
