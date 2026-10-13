from fastapi import FastAPI, Header, HTTPException
import requests

from mini_soc_config import evidence_dir, get_env

from collector.parsers.suricata_parser import parse as parse_suricata
from collector.parsers.nginx_access_parser import parse as parse_nginx_access
from collector.parsers.nginx_error_parser import parse as parse_nginx_error
from collector.parsers.auth_parser import parse as parse_auth
from collector.parsers.firewall_parser import parse as parse_firewall

app = FastAPI()


def parse_mini_soc_ids(line):
    return parse_suricata(line, log_type="mini_soc_ids")


BACKEND_URL = f"{get_env('BACKEND_URL', 'http://127.0.0.1:8000')}/api/ingest"

PARSERS = {
    "suricata": parse_suricata,
    "mini_soc_ids": parse_mini_soc_ids,
    "nginx_access": parse_nginx_access,
    "nginx_error": parse_nginx_error,
    "auth": parse_auth,
    "firewall": parse_firewall,
}


@app.on_event("startup")
def ensure_dirs():
    evidence_dir().mkdir(parents=True, exist_ok=True)


@app.get("/")
def health():
    return {"status": "collector running"}


def verify_agent_key(x_api_key):
    """Authenticate the log agent (task 3.1/3.4).

    The agent presents the ingest key as ``X-API-Key``.  When no key is
    configured (local development) authentication is skipped.
    """
    expected = get_env("INGEST_API_KEY")

    if not expected:
        return

    if x_api_key != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
        )


def _extract_lines(data):
    """Normalize both the batched and the legacy single-line request shapes.

    Batched (agent, task 3.4)::

        {"host": "...", "log_type": "auth", "lines": ["raw", ...]}

    Legacy (single line)::

        {"log_type": "auth", "raw": "raw"}
    """
    log_type = data.get("log_type")

    if not log_type:
        raise HTTPException(
            status_code=400,
            detail="log_type is required",
        )

    if "lines" in data:
        lines = data.get("lines")

        if not isinstance(lines, list):
            raise HTTPException(
                status_code=400,
                detail="lines must be a list",
            )

        return log_type, lines

    raw = data.get("raw")

    if not raw:
        raise HTTPException(
            status_code=400,
            detail="log_type and raw are required",
        )

    return log_type, [raw]


@app.post("/ingest")
def ingest(data: dict, x_api_key: str | None = Header(default=None)):
    verify_agent_key(x_api_key)

    log_type, lines = _extract_lines(data)

    parser = PARSERS.get(log_type)

    if parser is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported log_type: {log_type}",
        )

    events = []

    for line in lines:
        if not isinstance(line, str) or not line.strip():
            continue

        event = parser(line)

        if event is not None:
            events.append(event)

    if not events:
        raise HTTPException(
            status_code=422,
            detail="Could not parse log",
        )

    api_key = get_env("INGEST_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="INGEST_API_KEY is not configured",
        )

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }

    # Backend unreachable/timeout or a backend 5xx -> 503 so the log agent
    # knows to spool the batch and retry (contract: collector returns 503
    # when the backend is down; the agent then buffers).  A batch is forwarded
    # to the backend in a single POST.
    try:
        response = requests.post(
            BACKEND_URL,
            headers=headers,
            json={"events": events},
            timeout=10,
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=503,
            detail="backend unreachable; events not forwarded",
        )

    if response.status_code >= 500:
        raise HTTPException(
            status_code=503,
            detail=f"backend error (HTTP {response.status_code})",
        )

    return {
        "backend_status": response.status_code,
        "backend_response": response.text,
        "accepted": len(events),
    }
