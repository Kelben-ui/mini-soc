import json
import uuid
from datetime import datetime


def parse(line, log_type="suricata"):
    try:
        data = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return None

    timestamp = data.get("timestamp")
    if not timestamp:
        return None

    try:
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None

    alert = data.get("alert", {})
    metadata = data.get("metadata", {})

    src_port = data.get("src_port")
    dst_port = data.get("dest_port")

    # The backend requires ports to be between 1 and 65535.
    if not isinstance(src_port, int) or not 1 <= src_port <= 65535:
        src_port = None

    if not isinstance(dst_port, int) or not 1 <= dst_port <= 65535:
        dst_port = None

    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": timestamp,
        "host": data.get("host", "fw-01"),
        "log_type": log_type,
        "category": alert.get(
            "category",
            "intrusion_detection"
        ),
        "action": data.get("event_type", "alert"),
        "src_ip": data.get("src_ip"),
        "src_port": src_port,
        "dst_ip": data.get("dest_ip"),
        "dst_port": dst_port,
        "user": None,
        "outcome": alert.get("action"),
        "details": {
            "signature_id": alert.get("signature_id"),
            "signature": alert.get("signature"),
            "severity": alert.get("severity"),
            "gid": alert.get("gid"),
            "rev": alert.get("rev"),
            "proto": data.get("proto"),
            "count": metadata.get("count"),
        },
        "raw": line.strip(),
    }
