"""Collector ingest behavior: 503 when the backend is down (task 1.8)."""

import pytest
import requests
from fastapi import HTTPException

import collector.main as main

SOC_LINE = (
    '203.0.113.5 - - [iso=2026-10-13T09:15:00+00:00] '
    '"GET / HTTP/1.1" 200 10 "-" "curl/8.0" body='
)


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("INGEST_API_KEY", "test-key")


class _Response:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


def test_missing_fields_return_400():
    with pytest.raises(HTTPException) as exc:
        main.ingest({})

    assert exc.value.status_code == 400


def test_unsupported_log_type_returns_400():
    with pytest.raises(HTTPException) as exc:
        main.ingest({"log_type": "nope", "raw": "x"})

    assert exc.value.status_code == 400


def test_unparseable_line_returns_422():
    with pytest.raises(HTTPException) as exc:
        main.ingest({"log_type": "nginx_access", "raw": "garbage"})

    assert exc.value.status_code == 422


def test_backend_unreachable_returns_503(monkeypatch):
    def boom(*args, **kwargs):
        raise requests.ConnectionError("backend down")

    monkeypatch.setattr(main.requests, "post", boom)

    with pytest.raises(HTTPException) as exc:
        main.ingest({"log_type": "nginx_access", "raw": SOC_LINE})

    assert exc.value.status_code == 503


def test_backend_5xx_returns_503(monkeypatch):
    monkeypatch.setattr(
        main.requests,
        "post",
        lambda *a, **k: _Response(500, "boom"),
    )

    with pytest.raises(HTTPException) as exc:
        main.ingest({"log_type": "nginx_access", "raw": SOC_LINE})

    assert exc.value.status_code == 503


def test_backend_ok_returns_200(monkeypatch):
    monkeypatch.setattr(
        main.requests,
        "post",
        lambda *a, **k: _Response(201, "accepted"),
    )

    result = main.ingest({"log_type": "nginx_access", "raw": SOC_LINE})

    assert result["backend_status"] == 201