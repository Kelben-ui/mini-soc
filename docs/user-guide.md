# Mini SOC User Guide

## Start the backend

    cd ~/mini-soc/backend
    ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

Keep the terminal open when running the command in the foreground.

Check the backend from another terminal:

    curl -i http://127.0.0.1:8000/

A healthy backend returns HTTP 200.

## Check the collector

    curl -i http://127.0.0.1:9000/

The collector should return HTTP 200 when running.

## API documentation

With the backend running, open:

http://127.0.0.1:8000/docs

Use the interactive API documentation to review endpoints and perform
authorized tests.

## Start the frontend

    cd ~/mini-soc/frontend
    npm run dev

Open the local address printed by Vite. Confirm that the frontend API
configuration points to the intended backend address.

## Check processes and logs

    ps -eo pid,args | grep -E '[u]vicorn|[l]og_agent/agent.py'
    tail -n 30 /tmp/log_agent.log
    tail -n 30 /tmp/mini-soc-backend.log

The collector log location depends on how it was started.

## Troubleshooting

- If port 8000 is unavailable, inspect the backend process and its log.
- If port 9000 is unavailable, inspect the collector process and its log.
- If ingestion fails, check the collector's backend URL and API key.
- If database operations fail, check PostgreSQL and the root `.env`
  configuration without printing secrets.
- Check running processes before starting another agent instance.
- Review migration history before changing the database schema.

Only monitor systems you own or are authorized to test. Do not share secrets,
private keys, or unredacted sensitive logs.
