import re
import uuid

from datetime import datetime, timezone

from collector.parsers.common import get_hostname, to_utc_iso


LOG_PATTERN = re.compile(
    r'^(?P<timestamp>\d{4}/\d{2}/\d{2} '
    r'\d{2}:\d{2}:\d{2}) '
    r'\[(?P<level>\w+)\] '
    r'(?P<pid>\d+)#(?P<tid>\d+): '
    r'\*(?P<connection>\d+) '
    r'(?P<message>.*)$'
)


def parse(line):
    line = line.strip()

    match = LOG_PATTERN.match(line)

    if not match:
        return None

    data = match.groupdict()

    try:
        ts_dt = datetime.strptime(
            data["timestamp"],
            "%Y/%m/%d %H:%M:%S",
        )
    except ValueError:
        return None

    # nginx writes error-log timestamps in the host's LOCAL time with no
    # offset (unlike $time_iso8601 in the access log). Interpret them as local
    # time, then normalise to UTC: tagging a local time as UTC stores every
    # error event offset into the future whenever the host TZ is not UTC, which
    # also drags the detection window forward and suppresses alerts.
    ts_dt = ts_dt.astimezone(timezone.utc)

    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": to_utc_iso(ts_dt),
        "host": get_hostname(),
        "log_type": "nginx_error",
        "category": "web",
        "action": "error",
        "src_ip": None,
        "src_port": None,
        "dst_ip": None,
        "dst_port": None,
        "user": None,
        "outcome": data["level"],
        "details": {
            "level": data["level"],
            "pid": int(data["pid"]),
            "tid": int(data["tid"]),
            "connection": int(data["connection"]),
            "message": data["message"],
        },
        "raw": line,
    }