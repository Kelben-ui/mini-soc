from fastapi import FastAPI, HTTPException
import requests
import os

from collector.parsers.suricata_parser import parse as parse_suricata
from collector.parsers.nginx_access_parser import parse as parse_nginx_access
from collector.parsers.nginx_error_parser import parse as parse_nginx_error
from collector.parsers.auth_parser import parse as parse_auth
from collector.parsers.firewall_parser import parse as parse_firewall

app = FastAPI()


def parse_mini_soc_ids(line):
    return parse_suricata(line, log_type="mini_soc_ids")


BACKEND_URL = (
    f"{os.environ.get('BACKEND_URL', 'http://127.0.0.1:8000')}/api/ingest"
)

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
    evidence_dir = os.getenv("EVIDENCE_DIR", "/var/lib/mini-soc/evidence")
    os.makedirs(evidence_dir, exist_ok=True)


@app.get("/")
def health():
    return {"status": "collector running"}


@app.post("/ingest")
def ingest(data: dict):
    log_type = data.get("log_type")
    raw = data.get("raw")

    if not log_type or not raw:
        raise HTTPException(
            status_code=400,
            detail="log_type and raw are required"
        )

    parser = PARSERS.get(log_type)

    if parser is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported log_type: {log_type}"
        )

    event = parser(raw)

    if event is None:
        raise HTTPException(
            status_code=422,
            detail="Could not parse log"
        )

    api_key = os.environ.get("INGEST_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="INGEST_API_KEY is not configured"
        )

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

    # Backend unreachable/timeout or a backend 5xx -> 503 so the log agent
    # knows to buffer the line and retry (contract: collector returns 503
    # when the backend is down; the agent then buffers).
    try:
        response = requests.post(
            BACKEND_URL,
            headers=headers,
            json={"events": [event]},
            timeout=10
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=503,
            detail="backend unreachable; event not forwarded"
        )

    if response.status_code >= 500:
        raise HTTPException(
            status_code=503,
            detail=f"backend error (HTTP {response.status_code})"
        )

    return {
        "backend_status": response.status_code,
        "backend_response": response.text
    }