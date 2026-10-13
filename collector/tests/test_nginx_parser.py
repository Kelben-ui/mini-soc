from collector.parsers.common import get_hostname, get_private_ip
from collector.parsers.nginx_access_parser import parse

# Lines use the `soc` log_format from deploy/nginx/mini-soc.conf.
SOC_GET = (
    '203.0.113.5 - - [iso=2026-10-05T14:32:07+00:00] '
    '"GET /vulnerabilities/sqli/?id=%27+OR+1%3D1 HTTP/1.1" 200 1450 '
    '"-" "sqlmap/1.8" body='
)

SOC_POST = (
    '198.51.100.44 - - [iso=2026-10-05T14:33:01+00:00] '
    '"POST /login HTTP/1.1" 401 512 '
    '"http://127.0.0.1/login" "curl/8.0" '
    'body=username=admin%26password=%27+OR+%271%27%3D%271'
)

SOC_404 = (
    '192.0.2.99 - - [iso=2026-10-05T14:34:44+00:00] '
    '"GET /nonexistent HTTP/1.1" 404 153 '
    '"-" "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" body='
)


def test_get_is_normalized_with_http_request_action():
    result = parse(SOC_GET)

    assert result is not None
    assert result["log_type"] == "nginx_access"
    assert result["category"] == "web"
    assert result["action"] == "http_request"
    assert result["host"] == get_hostname()
    assert result["dst_ip"] == get_private_ip()
    assert result["dst_port"] == 80
    assert result["src_ip"] == "203.0.113.5"
    assert result["outcome"] == "success"


def test_uri_query_and_body_are_url_decoded_twice():
    result = parse(SOC_GET)

    details = result["details"]

    # %27+OR+1%3D1 -> ' OR 1=1 (unquote_plus turns '+' into a space).
    assert details["query"] == "id=' OR 1=1"
    assert details["uri"] == "/vulnerabilities/sqli/"
    assert details["method"] == "GET"
    assert details["status"] == 200
    assert details["bytes"] == 1450
    assert details["user_agent"] == "sqlmap/1.8"
    assert details["body"] == ""


def test_post_body_is_decoded_and_status_403_fails():
    result = parse(SOC_POST)

    assert result is not None
    assert result["outcome"] == "failure"
    assert result["details"]["status"] == 401
    assert result["details"]["body"] == "username=admin&password=' OR '1'='1"
    assert result["details"]["uri"] == "/login"
    assert result["details"]["query"] == ""


def test_missing_slash_line_returns_none():
    assert parse("127.0.0.1 GET /") is None
    assert parse("") is None
    assert parse("not an nginx line at all") is None


def test_details_contains_contract_keys():
    result = parse(SOC_404)

    assert result["details"].keys() >= {
        "method",
        "uri",
        "query",
        "status",
        "bytes",
        "user_agent",
        "body",
    }