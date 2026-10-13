from collector.parsers.common import get_hostname
from collector.parsers.nginx_error_parser import parse


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