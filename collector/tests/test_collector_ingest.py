"""Collector ingest behavior.

Covers the task 1.8 contract (503 when the backend is down) plus the Phase 3
task 3.4 batch shape and agent API-key auth.
"""

import pytest
import requests
from fastapi import HTTPException

import collector.main as main

SOC_LINE = (
    '203.0.113.5 - - [iso=2026-10-13T09:15:00+00:00] '
    '"GET / HTTP/1.1" 200 10 "-" "curl/8.0" body='
)

SOC_LINE_2 = (
    '198.51.100.9 - - [iso=2026-10-13T09:15:01+00:00] '
    '"GET /admin HTTP/1.1" 404 10 "-" "curl/8.0" body='
)

KEY = "test-key"


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("INGEST_API_KEY", KEY)


class _Response:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


def test_missing_api_key_returns_401():
    with pytest.raises(HTTPException) as exc:
        main.ingest({"log_type": "nginx_access", "raw": SOC_LINE})

    assert exc.value.status_code == 401


def test_wrong_api_key_returns_401():
    with pytest.raises(HTTPException) as exc:
        main.ingest(
            {"log_type": "nginx_access", "raw": SOC_LINE},
            x_api_key="nope",
        )

    assert exc.value.status_code == 401


def test_missing_fields_return_400():
    with pytest.raises(HTTPException) as exc:
        main.ingest({}, x_api_key=KEY)

    assert exc.value.status_code == 400


def test_unsupported_log_type_returns_400():
    with pytest.raises(HTTPException) as exc:
        main.ingest({"log_type": "nope", "raw": "x"}, x_api_key=KEY)

    assert exc.value.status_code == 400


def test_unparseable_line_returns_422(capsys):
    with pytest.raises(HTTPException) as exc:
        main.ingest({"log_type": "nginx_access", "raw": "garbage"}, x_api_key=KEY)

    assert exc.value.status_code == 422

    # The rejection is logged with a sample of the offending line.
    out = capsys.readouterr().out
    assert "422 could not parse" in out
    assert "garbage" in out


def test_bad_lines_type_returns_400():
    with pytest.raises(HTTPException) as exc:
        main.ingest(
            {"log_type": "nginx_access", "lines": "not-a-list"},
            x_api_key=KEY,
        )

    assert exc.value.status_code == 400


def test_backend_unreachable_returns_503(monkeypatch):
    def boom(*args, **kwargs):
        raise requests.ConnectionError("backend down")

    monkeypatch.setattr(main.requests, "post", boom)

    with pytest.raises(HTTPException) as exc:
        main.ingest({"log_type": "nginx_access", "raw": SOC_LINE}, x_api_key=KEY)

    assert exc.value.status_code == 503


def test_backend_5xx_returns_503(monkeypatch):
    monkeypatch.setattr(
        main.requests,
        "post",
        lambda *a, **k: _Response(500, "boom"),
    )

    with pytest.raises(HTTPException) as exc:
        main.ingest({"log_type": "nginx_access", "raw": SOC_LINE}, x_api_key=KEY)

    assert exc.value.status_code == 503


def test_backend_ok_returns_200(monkeypatch):
    monkeypatch.setattr(
        main.requests,
        "post",
        lambda *a, **k: _Response(201, "accepted"),
    )

    result = main.ingest({"log_type": "nginx_access", "raw": SOC_LINE}, x_api_key=KEY)

    assert result["backend_status"] == 201
    assert result["accepted"] == 1


def test_batch_is_forwarded_in_one_post(monkeypatch):
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(json)
        return _Response(201, "accepted")

    monkeypatch.setattr(main.requests, "post", fake_post)

    result = main.ingest(
        {"host": "h", "log_type": "nginx_access", "lines": [SOC_LINE, SOC_LINE_2]},
        x_api_key=KEY,
    )

    assert len(calls) == 1  # one POST per batch (task 3.4)
    assert len(calls[0]["events"]) == 2
    assert result["accepted"] == 2
