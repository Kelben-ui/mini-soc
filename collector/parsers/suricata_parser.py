"""Normalizer for Suricata-style JSON and the Mini SOC IDS output
(/var/log/mini_soc_ids.json).

Per the frozen contract (docs/contracts.md §2.6):

- generic alerts            -> category ``ids``,      action ``ids_alert``
- port-scan signatures      -> category ``network``,  action ``port_scan``
- dns events                -> category ``dns``,      action ``unusual_dns``
- outbound-connection events-> category ``network``,  action ``unusual_outbound``

``details`` carries ``{signature_id, signature, priority, count}`` with
``priority`` taken from the IDS ``priority`` field or falling back to
``severity``.
"""

import json
import re
import uuid

from datetime import datetime

from collector.parsers.common import get_hostname, to_utc_iso

# Custom Mini SOC IDS signature that describes a port scan (see
# ids/live_ids_ips.py / infrastructure/fw-01/live_ids_ips.py).
PORT_SCAN_SIGNATURE_IDS = {9000001}

DNS_EVENT_TYPES = {"dns", "dns_query"}
OUTBOUND_EVENT_TYPES = {"outbound", "outbound_connection"}

_OFFSET = re.compile(r"([+-]\d{2})(\d{2})$")


def _to_utc(timestamp):
    ts = timestamp.replace("Z", "+00:00")

    # Python < 3.11 needs a colon in the offset ("+0000" -> "+00:00").
    if _OFFSET.search(ts):
        ts = _OFFSET.sub(r"\1:\2", ts)

    return datetime.fromisoformat(ts)


def parse(line, log_type="suricata"):
    try:
        data = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return None

    timestamp = data.get("timestamp")

    if not timestamp:
        return None

    try:
        dt = _to_utc(timestamp)
    except (ValueError, TypeError):
        return None

    alert = data.get("alert") or {}
    metadata = data.get("metadata") or {}
    event_type = data.get("event_type", "alert")

    if event_type in DNS_EVENT_TYPES:
        category, action = "dns", "unusual_dns"
    elif event_type in OUTBOUND_EVENT_TYPES:
        category, action = "network", "unusual_outbound"
    elif alert.get("signature_id") in PORT_SCAN_SIGNATURE_IDS:
        category, action = "network", "port_scan"
    else:
        category, action = "ids", "ids_alert"

    src_port = data.get("src_port")
    dst_port = data.get("dest_port")

    # The backend requires ports to be between 1 and 65535.
    if not isinstance(src_port, int) or not 1 <= src_port <= 65535:
        src_port = None

    if not isinstance(dst_port, int) or not 1 <= dst_port <= 65535:
        dst_port = None

    priority = alert.get("priority", alert.get("severity"))

    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": to_utc_iso(dt),
        "host": get_hostname(),
        "log_type": log_type,
        "category": category,
        "action": action,
        "src_ip": data.get("src_ip"),
        "src_port": src_port,
        "dst_ip": data.get("dest_ip"),
        "dst_port": dst_port,
        "user": None,
        "outcome": alert.get("action"),
        "details": {
            "signature_id": alert.get("signature_id"),
            "signature": alert.get("signature"),
            "priority": priority,
            "count": metadata.get("count"),
        },
        "raw": line.strip(),
    }