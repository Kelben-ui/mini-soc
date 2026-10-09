import re
import uuid
from datetime import datetime


LOG_PATTERN = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ '
    r'\[(?P<timestamp>[^\]]+)\] '
    r'"(?P<method>\S+) (?P<path>\S+) (?P<protocol>[^"]+)" '
    r'(?P<status>\d{3}) (?P<bytes>\S+) '
    r'"(?P<referer>[^"]*)" '
    r'"(?P<user_agent>[^"]*)"'
)


def parse(line):
    match = LOG_PATTERN.match(line.strip())

    if not match:
        return None

    data = match.groupdict()

    try:
        timestamp = datetime.strptime(
            data["timestamp"],
            "%d/%b/%Y:%H:%M:%S %z"
        )
    except ValueError:
        return None

    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": timestamp.isoformat(),
        "host": "web-01",
        "log_type": "nginx_access",
        "category": "web",
        "action": data["method"],
        "src_ip": data["ip"],
        "src_port": None,
        "dst_ip": None,
        "dst_port": None,
        "user": None,
        "outcome": data["status"],
        "details": {
            "path": data["path"],
            "protocol": data["protocol"],
            "status": int(data["status"]),
            "bytes": data["bytes"],
            "referer": data["referer"],
            "user_agent": data["user_agent"],
        },
        "raw": line.strip(),
    }
