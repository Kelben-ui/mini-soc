# Log Agent (`agents/`)

The host-side **log shipper**. It tails the instance's log sources, batches
lines per source, and POSTs them to the central collector. It is deliberately
dumb: every path, URL and batch size comes from configuration, never from code.

## Layout

| Path | Role |
|---|---|
| `log_agent/agent.py` | Entry point and run loop (`python -m agents.log_agent.agent`). |
| `log_agent/config.py` | Loads `/etc/mini-soc/agent.yaml`, then applies environment overrides. |
| `log_agent/tailer.py` | Follows a file and survives rotation / truncation. |
| `log_agent/offsets.py` | Persists `(path, inode)` offsets so a restart never loses or duplicates a line. |
| `log_agent/sender.py` | Batches lines and POSTs them; spools to disk when the collector is unavailable. |
| `log_agent/heartbeat.py` | Periodic liveness beacon to the backend. |
| `log_agent/tests/` | Unit tests — run with `pytest agents`. |
| [`agent.example.yaml`](agent.example.yaml) | Template, installed to `/etc/mini-soc/agent.yaml` by `deploy/install.sh`. |

## Sources watched

| Source | `log_type` | Notes |
|---|---|---|
| `/var/log/nginx/access.log` | `nginx_access` | Uses the `soc` format, which appends `body=...`. |
| `/var/log/nginx/error.log` | `nginx_error` | |
| `/var/log/auth.log` | `auth` | SSH logins/failures. |
| `/var/log/mini_soc_ids.json` | `mini_soc_ids` | Suricata-style JSON from the custom IDS. |
| kernel firewall log (via `journalctl -k`) | `firewall` | nftables `SOC_DROP:` / `SOC_ACCEPT:` / `SOC_OUT:` lines. |

## Batching, offsets and spooling

- Lines are batched **per source**: sent when `batch_size` lines accumulate or
  `batch_timeout` seconds elapse, as one
  `{"host": ..., "log_type": ..., "lines": [...]}` request to
  `COLLECTOR_INGEST_URL` (default `http://127.0.0.1:9000/ingest`) with the
  `X-Ingest-Key` header.
- File offsets are kept in `/var/lib/mini-soc/agent/state.json` keyed by
  `(path, inode)`, so rotation and restarts neither drop nor duplicate lines.
- If the collector is unreachable, batches are spooled under
  `/var/lib/mini-soc/agent/spool/` and retried; failed sends are never silently
  dropped.
- A heartbeat is sent every `heartbeat_interval` seconds to
  `HEARTBEAT_URL` (default `http://127.0.0.1:8000/api/agents/heartbeat`).

## Configuration

`/etc/mini-soc/agent.yaml` (installed from `agent.example.yaml`, mode `0640`).
Environment variables override YAML. See `log_agent/config.py` for the full list
(`COLLECTOR_INGEST_URL` / `COLLECTOR_URL`, `HEARTBEAT_URL`, `AGENT_HOST`, batch
sizes, watched `sources`, etc.).

## Running

```bash
# Tests
pytest agents -q

# One-shot / foreground run (dev)
python -m agents.log_agent.agent --config /etc/mini-soc/agent.yaml
```

In production it runs as the `soc-agent` systemd unit
(`deploy/systemd/soc-agent.service`), started by `deploy/install.sh`.
