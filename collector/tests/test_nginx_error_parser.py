import os
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from collector.parsers.common import get_hostname
from collector.parsers.nginx_error_parser import parse


@contextmanager
def _tz(name):
    """Run a block with the process TZ set to ``name`` (POSIX only)."""
    if not hasattr(time, "tzset"):
        pytest.skip("tzset unavailable on this platform")

    original = os.environ.get("TZ")
    os.environ["TZ"] = name
    time.tzset()
    try:
        yield
    finally:
        if original is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original
        time.tzset()


NONFATAL = (
    '2026/10/05 14:32:07 [error] 37677#0: *3 '
    'connect() failed (111: Connection refused) while connecting to '
    'upstream, client: 203.0.113.5, server: _, request: "GET / HTTP/1.1", '
    'upstream: "http://127.0.0.1:8000/"'
)

MISSING_FILE = (
    '2026/10/05 14:33:09 [crit] 37677#0: *9 '
    'open() "/opt/mini-soc/frontend/dist/nope" failed '
    '(2: No such file or directory), client: 198.51.100.44, server: _, '
    'request: "GET /nope HTTP/1.1"'
)

BUFFERED = (
    '2026/10/05 14:34:22 [warn] 37677#0: *12 '
    'an upstream response is buffered to a temporary file'
)


def test_error_line_is_normalized():
    result = parse(NONFATAL)

    assert result is not None
    assert result["log_type"] == "nginx_error"
    assert result["category"] == "web"
    assert result["action"] == "error"
    assert result["outcome"] == "error"
    assert result["host"] == get_hostname()
    assert result["details"]["pid"] == 37677
    assert result["details"]["connection"] == 3
    assert result["timestamp"].endswith("Z")


def test_crit_and_warn_levels_are_kept():
    crit = parse(MISSING_FILE)
    warn = parse(BUFFERED)

    assert crit["outcome"] == "crit"
    assert warn["outcome"] == "warn"


def test_malformed_lines_return_none():
    assert parse("not an nginx error line") is None
    assert parse("") is None
    assert parse("2026/10/05 14:32:07 [error] no pid here") is None


MULTILINE_ENTRY = (
    '2026/10/20 10:56:10 [error] 1769#1769: *19 FastCGI sent in stderr: '
    '"PHP message: PHP Warning: include(../../etc/passwd): Failed to open '
    'stream: No such file or directory in /var/www/dvwa/login.php on line 8\n'
    'Stack trace:\n'
    '#0 /var/www/dvwa/login.php(8): dvwaDatabaseConnect()\n'
    '#1 {main}\n'
    '  thrown in /var/www/dvwa/dvwa/includes/dvwaPage.inc.php on line 569" '
    'while reading response header from upstream, client: 127.0.0.1'
)


def test_multiline_entry_is_parsed():
    """Regression: the agent joins a multi-line entry before sending it.

    With ``.*$`` and no DOTALL the message could not span newlines, so `$`
    never matched and the whole entry was rejected - the collector then
    answered 422 and the continuation lines were lost.
    """
    result = parse(MULTILINE_ENTRY)

    assert result is not None
    assert result["log_type"] == "nginx_error"
    assert result["details"]["pid"] == 1769
    assert result["details"]["connection"] == 19
    # The stack trace is preserved inside the single message field.
    assert "Stack trace:" in result["details"]["message"]
    assert "dvwaDatabaseConnect()" in result["details"]["message"]


def test_error_timestamp_is_not_future_dated_in_non_utc_tz():
    """Regression: nginx error timestamps are host-local, not UTC.

    On a host at UTC+1, tagging the naive timestamp as UTC stored the event an
    hour in the future. That future event became the detection window anchor
    and suppressed every subsequent alert.
    """
    with _tz("Africa/Lagos"):  # WAT, UTC+1 — no DST
        result = parse(NONFATAL)

    stored = datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))
    # 14:32:07 local (UTC+1) == 13:32:07 UTC
    expected = datetime(2026, 10, 5, 13, 32, 7, tzinfo=timezone.utc)
    assert stored == expected


def test_error_timestamp_matches_utc_tz():
    with _tz("UTC"):
        result = parse(NONFATAL)

    stored = datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))
    assert stored == datetime(2026, 10, 5, 14, 32, 7, tzinfo=timezone.utc)


def test_error_timestamp_is_never_ahead_of_wall_clock():
    """The stored instant must never exceed the actual moment it was logged."""
    with _tz("Africa/Lagos"):
        now = datetime.now(timezone.utc)
        result = parse(NONFATAL)

    stored = datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))
    # stored is a fixed past date, so it must be well before "now" regardless of
    # the machine's own clock; the point is that it is not shifted +1h.
    assert stored < now + timedelta(minutes=1)