import re
import uuid
from datetime import datetime


LOG_PATTERN = re.compile(
    r'^(?P<timestamp>\d{4}/\d{2}/\d{2} '
    r'\d{2}:\d{2}:\d{2}) '
    r'\[(?P<level>\w+)\] '
    r'(?P<pid>\d+)#(?P<tid>\d+): '
    r'\*(?P<connection>\d+) '
    r'(?P<message>.*)$'
)


def parse(line):
    match = LOG_PATTERN.match(line.strip())

    if not match:
        return None

    data = match.groupdict()

    try:
        timestamp = datetime.strptime(
            data["timestamp"],
            "%Y/%m/%d %H:%M:%S"
        )
    except ValueError:
        return None

    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": timestamp.isoformat(),
        "host": "web-01",
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
        "raw": line.strip(),
    }
