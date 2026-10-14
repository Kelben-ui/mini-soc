# Collector (`collector/`)

The **normalization service**. It accepts raw log batches from the log agent,
parses each line into the platform's common event schema
([`../docs/contracts.md`](../docs/contracts.md) §3), and forwards the events to
the backend's ingest API. It is the only component that understands raw log
formats.

## Service

- FastAPI app (`collector/main.py`), bound to `127.0.0.1:9000`.
- `POST /ingest` — accepts `{"host", "log_type", "lines": [...]}` (batched) or
  the legacy single-line shape. Requires the `X-Ingest-Key` header matching
  `INGEST_API_KEY` (auth is skipped when the variable is unset, for local dev).
- `GET /` — liveness.
- Parsed events are POSTed to the backend ingest API
  (`BACKEND_URL` + `/api/ingest`, default `http://127.0.0.1:8000/api/ingest`).

## Parsers

| File | `log_type` | Produces |
|---|---|---|
| `parsers/nginx_access_parser.py` | `nginx_access` | `category: web`, `action: http_request` (+ decoded `uri`/`query`/`body`). |
| `collector/parsers/nginx_error_parser.py` | `nginx_error` | nginx error events. |
| `collector/parsers/auth_parser.py` | `auth` | `ssh_login` success/failure events. |
| `collector/parsers/firewall_parser.py` | `firewall` | nftables `SOC_DROP:`/`SOC_ACCEPT:`/`SOC_OUT:` → network events. |
| `collector/parsers/suricata_parser.py` | `mini_soc_ids` | Suricata-style JSON from the custom IDS: generic alerts → `ids`/`ids_alert`; port scan (9000001) → `network`/`port_scan`; DNS (9000004) → `dns`/`unusual_dns`; outbound (9000005) → `network`/`unusual_outbound`. |
| `collector/parsers/common.py` | — | Shared schema helpers (event IDs, timestamps, host/agent fields). |

Every parser returns a single normalized dict or `None` for a line it cannot
parse; the collector logs and skips unparseable lines rather than failing the
batch.

## Tests

```bash
pytest collector -q
```

Each parser has a matching `collector/tests/test_*_parser.py`. Live ingestion is
covered by `collector/tests/test_collector_ingest.py`.

## Running

```bash
uvicorn collector.main:app --host 127.0.0.1 --port 9000
```

Production: the `soc-collector` systemd unit
(`../deploy/systemd/soc-collector.service`).

## Related

- Event schema: [`../docs/contracts.md`](../docs/contracts.md) §3.
- Log agent that feeds it: [`../agents/`](../agents/).
