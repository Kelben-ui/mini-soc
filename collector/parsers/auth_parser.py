import re
import uuid
from datetime import datetime


def parse(line):
    line = line.strip()

    match = re.match(
        r'^(?P<timestamp>\S+) '
        r'(?P<host>\S+) '
        r'(?P<process>[^:]+): '
        r'(?P<message>.*)$',
        line
    )

    if not match:
        return None

    data = match.groupdict()

    try:
        timestamp = datetime.fromisoformat(data["timestamp"])
    except ValueError:
        return None

    message = data["message"]

    src_ip = None
    src_port = None
    user = None
    action = "authentication"
    outcome = "unknown"

    accepted = re.search(
        r'Accepted \S+ for (\S+) from (\S+) port (\d+)',
        message
    )

    failed = re.search(
        r'Failed \S+ for (?:invalid user )?(\S+) from (\S+) port (\d+)',
        message
    )

    invalid_user = re.search(
        r'Invalid user (\S+) from (\S+) port (\d+)',
        message
    )

    if accepted:
        user = accepted.group(1)
        src_ip = accepted.group(2)
        src_port = int(accepted.group(3))
        action = "ssh_login"
        outcome = "success"

    elif failed:
        user = failed.group(1)
        src_ip = failed.group(2)
        src_port = int(failed.group(3))
        action = "ssh_login"
        outcome = "failure"

    elif invalid_user:
        user = invalid_user.group(1)
        src_ip = invalid_user.group(2)
        src_port = int(invalid_user.group(3))
        action = "ssh_login"
        outcome = "failure"

    elif "sudo:" in data["process"] or "sudo:" in line:
        action = "sudo"
        outcome = "activity"

    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": timestamp.isoformat(),
        "host": data["host"],
        "log_type": "auth",
        "category": "authentication",
        "action": action,
        "src_ip": src_ip,
        "src_port": src_port,
        "dst_ip": None,
        "dst_port": 22 if action == "ssh_login" else None,
        "user": user,
        "outcome": outcome,
        "details": {
            "process": data["process"],
            "message": message,
        },
        "raw": line,
    }
