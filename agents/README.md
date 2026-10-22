# Log Agent (`agents/`)

The host-side **log shipper**. It tails the instance's log sources, batches
lines per source, and POSTs them to the central collector. It is deliberately
dumb: every path, URL and batch size comes from configuration, never from code.

## Layout

| Path | Role |
|---|---|
| `log_agent/agent.py` | Entry point and run loop (`python -m agents.log_agent.agent`). |
| `log_agent/config.py` | Loads `agents/agent.yaml` (repo; `$AGENT_CONFIG` overrides), then applies environment overrides. |
| `log_agent/tailer.py` | Follows a file and survives rotation / truncation. |
| `log_agent/offsets.py` | Persists `(path, inode)` offsets so a restart never loses or duplicates a line. |
| `log_agent/sender.py` | Batches lines and POSTs them; spools to disk when the collector is unavailable. |
| `log_agent/heartbeat.py` | Periodic liveness beacon to the backend. |
| `log_agent/tests/` | Unit tests — run with `pytest agents`. |
| [`agent.example.yaml`](agent.example.yaml) | Template — copy to `agents/agent.yaml` (the live config). |

## Sources watched

| Source | `log_type` | Notes |
|---|---|---|
| `/var/log/nginx/access.log` | `nginx_access` | Uses the `soc` format, which appends `body=...`. |
| `/var/log/nginx/error.log` | `nginx_error` | |
| `/var/log/auth.log` | `auth` | SSH logins/failures. |
| `/var/log/mini_soc_ids.json` | `mini_soc_ids` | Suricata-style JSON from the custom IDS. |
| kernel firewall log (via `journalctl -k`) | `firewall` | nftables `SOC_DROP:` / `SOC_ACCEPT:` / `SOC_OUT:` lines. |

## Batching, offsets and spooling

- Lines are batched **per source**: sent when `batch.max_lines` lines accumulate
  or `batch.max_seconds` seconds elapse, as one
  `{"host": ..., "log_type": ..., "lines": [...]}` request to
  `collector_url` / `COLLECTOR_INGEST_URL` (default
  `http://127.0.0.1:9000/ingest`) with the `X-API-Key` header.
- File offsets are kept in `/var/lib/mini-soc/agent/state.json` keyed by
  `(path, inode)`, so rotation and restarts neither drop nor duplicate lines.
- If the collector is unreachable (connection error, timeout or a 5xx), batches
  are spooled under `/var/lib/mini-soc/agent/spool/` and replayed FIFO with
  backoff. A 4xx (e.g. `422` for lines no parser accepts) is treated as
  delivered, since retrying it forever would only grow the spool.
- A heartbeat is sent every `heartbeat.seconds` / `AGENT_HEARTBEAT_SECONDS`
  (default 30 s) to `heartbeat.url` (default
  `http://127.0.0.1:8000/api/agents/heartbeat`).

## Configuration

`agents/agent.yaml` (copied from `agent.example.yaml`).
Environment variables override YAML. See `log_agent/config.py` for the full list
(`COLLECTOR_INGEST_URL` / `COLLECTOR_URL`, `BACKEND_URL` for the heartbeat,
`SOC_HOSTNAME`, `INGEST_API_KEY`, `AGENT_CONFIG`, `AGENT_BUFFER_DIR`,
`AGENT_HEARTBEAT_SECONDS`). Watched sources are configured under `files:` /
`journal:` in the YAML only.

## Running

```bash
# Tests
pytest agents -q

# One-shot / foreground run (dev); reads $AGENT_CONFIG,
# default <repo>/agents/agent.yaml
python -m agents.log_agent.agent
```

In production it runs as the `soc-agent` systemd unit
(`deploy/systemd/soc-agent.service`), started by `deploy/install.sh`.
