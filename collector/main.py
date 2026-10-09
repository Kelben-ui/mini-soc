from fastapi import FastAPI, HTTPException
import requests
import os

from collector.parsers.suricata_parser import parse as parse_suricata
def parse_mini_soc_ids(line):
    return parse_suricata(line, log_type="mini_soc_ids")
from collector.parsers.nginx_access_parser import parse as parse_nginx_access
from collector.parsers.nginx_error_parser import parse as parse_nginx_error
from collector.parsers.auth_parser import parse as parse_auth

app = FastAPI()

BACKEND_URL = "http://127.0.0.1:8000/api/ingest"

PARSERS = {
    "suricata": parse_suricata,
    "mini_soc_ids": parse_mini_soc_ids,
    "nginx_access": parse_nginx_access,
    "nginx_error": parse_nginx_error,
    "auth": parse_auth,
}


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

    response = requests.post(
        BACKEND_URL,
        headers=headers,
        json={"events": [event]},
        timeout=10
    )

    return {
        "backend_status": response.status_code,
        "backend_response": response.text
    }
