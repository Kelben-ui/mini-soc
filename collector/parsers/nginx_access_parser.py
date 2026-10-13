import re
import uuid

from datetime import datetime
from urllib.parse import unquote_plus

from collector.parsers.common import get_hostname, get_private_ip, to_utc_iso

# Matches the `soc` log format defined in deploy/nginx/mini-soc.conf:
#
#   $remote_addr - $remote_user [iso=$time_iso8601]
#   "$request_method $request_uri $server_protocol" $status $body_bytes_sent
#   "$http_referer" "$http_user_agent" body=$request_body
#
# `$time_iso8601` carries the UTC offset, `body=` is placed at the end of the
# line so payloads containing quotes or newlines cannot break parsing.
LOG_PATTERN = re.compile(
    r'^(?P<ip>\S+) - (?P<remote_user>\S+) '
    r'\[iso=(?P<timestamp>[^\]]+)\] '
    r'"(?P<method>\S+) (?P<request_uri>\S+) (?P<protocol>[^"]*)" '
    r'(?P<status>\d{3}) (?P<bytes>\d+) '
    r'"(?P<referer>[^"]*)" '
    r'"(?P<user_agent>[^"]*)" '
    r'body=(?P<body>.*)$'
)


def _decode(value):
    """URL-decode a value twice (defeats single/double encoding)."""
    if value is None:
        return None
    return unquote_plus(unquote_plus(value))


def parse(line):
    line = line.strip()

    match = LOG_PATTERN.match(line)

    if not match:
        return None

    data = match.groupdict()

    request_uri = data["request_uri"]

    # Split $request_uri into path and query string.
    if "?" in request_uri:
        raw_uri, raw_query = request_uri.split("?", 1)
    else:
        raw_uri, raw_query = request_uri, ""

    uri = _decode(raw_uri)
    query = _decode(raw_query)
    body = _decode(data["body"])

    status = int(data["status"])

    remote_user = data["remote_user"]
    user = None if remote_user in ("-", "") else remote_user

    try:
        timestamp = to_utc_iso(datetime.fromisoformat(data["timestamp"]))
    except ValueError:
        return None

    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": timestamp,
        "host": get_hostname(),
        "log_type": "nginx_access",
        "category": "web",
        "action": "http_request",
        "src_ip": data["ip"] if data["ip"] not in ("-", "") else None,
        "src_port": None,
        "dst_ip": get_private_ip(),
        "dst_port": 80,
        "user": user,
        "outcome": "success" if status < 400 else "failure",
        "details": {
            "method": data["method"],
            "uri": uri,
            "query": query,
            "status": status,
            "bytes": int(data["bytes"]),
            "user_agent": data["user_agent"],
            "body": body,
        },
        "raw": line,
    }