"""Parser for systemd/rsyslog ``auth.log`` lines.

Real lines look like:

    Oct 13 09:11:02 ip-172-31-13-199 sshd[2203]: Failed password for root
    from 203.0.113.9 port 52820 ssh2

    Oct 13 09:14:01 ip-172-31-13-199 sshd[2261]: Accepted publickey for
    ubuntu from 143.105.152.60 port 52313 ssh2: RSA SHA256:abc...

SSH login events get ``action: ssh_login`` and ``dst_ip`` set to the
instance private IP (port 22).  ``message repeated N times`` summary
lines are ignored (the original lines are already counted).
"""

import re
import uuid

from datetime import datetime, timezone

from collector.parsers.common import get_hostname, get_private_ip, to_utc_iso

LINE_PATTERN = re.compile(
    r'^(?P<timestamp>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}) '
    r'(?P<log_host>\S+) '
    r'(?P<process>[^:]+): '
    r'(?P<message>.*)$'
)

ACCEPTED = re.compile(
    r'Accepted \S+ for (\S+) from (\S+) port (\d+)'
)
FAILED = re.compile(
    r'Failed \S+ for (?:invalid user )?(\S+) from (\S+) port (\d+)'
)
INVALID_USER = re.compile(
    r'Invalid user (\S+) from (\S+) port (\d+)'
)


def parse(line):
    line = line.strip()

    match = LINE_PATTERN.match(line)

    if not match:
        return None

    data = match.groupdict()

    message = data["message"]

    # rsyslog collapses repeats like:
    #   message repeated 2 times: [ Failed password for root ... ]
    # Skip them so repeated flood lines are not double-counted.
    if "message repeated" in message.lower():
        return None

    try:
        ts_dt = datetime.strptime(
            f"{datetime.now(timezone.utc).year} {data['timestamp']}",
            "%Y %b %d %H:%M:%S",
        )
    except ValueError:
        return None

    ts_dt = ts_dt.replace(tzinfo=timezone.utc)

    src_ip = None
    src_port = None
    user = None
    action = "authentication"
    outcome = "unknown"

    accepted = ACCEPTED.search(message)
    failed = FAILED.search(message)
    invalid_user = INVALID_USER.search(message)

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

    elif "sudo" in data["process"].lower() or "sudo:" in line.lower():
        action = "sudo"
        outcome = "activity"

    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": to_utc_iso(ts_dt),
        "host": get_hostname(),
        "log_type": "auth",
        "category": "authentication",
        "action": action,
        "src_ip": src_ip,
        "src_port": src_port,
        "dst_ip": get_private_ip() if action == "ssh_login" else None,
        "dst_port": 22 if action == "ssh_login" else None,
        "user": user,
        "outcome": outcome,
        "details": {
            "process": data["process"],
            "message": message,
        },
        "raw": line,
    }