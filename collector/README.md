# Collector (`collector/`)

The **normalization service**. It accepts raw log batches from the log agent,
parses each line into the platform's common event schema
([`../docs/contracts.md`](../docs/contracts.md) §3), and forwards the events to
the backend's ingest API. It is the only component that understands raw log
formats.

## Service

- FastAPI app (`collector/main.py`), bound to `127.0.0.1:9000`.
- `POST /ingest` — accepts `{"host", "log_type", "lines": [...]}` (batched) or
  the legacy single-line shape. Requires the `X-API-Key` header matching
  `INGEST_API_KEY` (auth is skipped when the variable is unset, for local dev).
- `GET /` — liveness.
- Parsed events are POSTed to the backend ingest API
  (`BACKEND_URL` + `/api/ingest`, default `http://127.0.0.1:8000/api/ingest`).

## Parsers

| File | `log_type` | Produces |
|---|---|---|
| `parsers/nginx_access_parser.py` | `nginx_access` | `category: web`, `action: http_request` (+ decoded `uri`/`query`/`body`). |
| `collector/parsers/nginx_error_parser.py` | `nginx_error` | nginx error events (naive local timestamps converted to UTC — see [Timestamps](#timestamps)). |
| `collector/parsers/auth_parser.py` | `auth` | `ssh_login` success/failure events. |
| `collector/parsers/firewall_parser.py` | `firewall` | nftables `SOC_DROP:`/`SOC_ACCEPT:`/`SOC_OUT:` → network events. |
| `collector/parsers/suricata_parser.py` | `mini_soc_ids` | Suricata-style JSON from the custom IDS: generic alerts → `ids`/`ids_alert`; port scan (9000001) → `network`/`port_scan`; DNS (9000004) → `dns`/`unusual_dns`; outbound (9000005) → `network`/`unusual_outbound`. |
| `collector/parsers/common.py` | — | Shared schema helpers (event IDs, timestamps, host/agent fields). |

Every parser returns a single normalized dict or `None` for a line it cannot
parse; the collector logs and skips unparseable lines rather than failing the
batch.

### Timestamps

Every event timestamp is stored as **UTC**
([`../docs/contracts.md`](../docs/contracts.md) §2.5). Most sources already
carry an offset (`+00:00`, `Z`, `-o short-iso`), so they are converted
directly. One does not: **nginx's error log** writes a naive local timestamp
with no zone (`2026/10/20 09:58:42`).

`nginx_error_parser.py` treats that value as *local time* and normalises it:

```python
ts_dt.astimezone(timezone.utc)   # naive -> local -> UTC
```

Do **not** use `ts_dt.replace(tzinfo=timezone.utc)` here. `replace` merely
*relabels* the naive value as UTC, so on a host whose TZ is not UTC the stored
instant is wrong by the UTC offset. On `Africa/Lagos` (UTC+1) every
`nginx_error` event landed an hour in the future; because
`detection/engine/engine.py` anchors its detection window on the **newest**
event, those future rows pushed the window past all real traffic and **no
alerts were produced at all**. The bug is invisible on a UTC host (the lab
EC2), which is why it survived until the local non-UTC run —
see [`../docs/testing/local-wsl-run.md`](../docs/testing/local-wsl-run.md).

`collector/tests/test_nginx_error_parser.py` pins this down with a
`TZ=Africa/Lagos` regression test plus a "no event may be dated in the
future" assertion.

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
