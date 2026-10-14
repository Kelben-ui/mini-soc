"""Parser for nftables log lines emitted to the kernel journal/kern.log.

Format (rsyslog kern.log):

    Oct 13 09:11:02 ip-172-31-13-199 kernel: SOC_DROP: IN=eth0 OUT=
    MAC=... SRC=203.0.113.5 DST=172.31.13.199 ... PROTO=TCP SPT=34567
    DPT=443 SYN URGP=0

Also accepts the two journald forms:

* ``journalctl -o short-iso`` (the log agent's firewall source, task 3.6):
  ``2026-10-13T09:11:02+0000 host kernel: SOC_DROP: IN=...``.  Newer systemd
  emits an RFC 3339 offset with a colon (``+00:00``), so both forms are
  accepted.
* ``journalctl -o cat``, which carries no timestamp
  (SOC_DROP: IN=...), which then defaults to the current UTC time.

Prefix -> action mapping: SOC_DROP -> drop, SOC_ACCEPT -> accept,
SOC_OUT -> out (kept out of ``unusual_outbound`` so every outbound flow
does not create an alert).
"""

import re
import uuid

from datetime import datetime, timezone

from collector.parsers.common import get_hostname, to_utc_iso

LINE_PATTERN = re.compile(
    r'^(?P<timestamp>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}) '
    r'(?P<kernel_host>\S+) kernel: '
    r'(?P<prefix>SOC_DROP|SOC_ACCEPT|SOC_OUT): '
    r'(?P<payload>.*)$'
)

# journalctl -o short-iso: 2026-10-13T09:11:02+0000 host kernel: SOC_DROP: ...
# (newer systemd: ...T09:11:02+00:00 -- colon in the offset).
ISO_PATTERN = re.compile(
    r'^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:?\d{2}) '
    r'(?P<kernel_host>\S+) kernel: '
    r'(?P<prefix>SOC_DROP|SOC_ACCEPT|SOC_OUT): '
    r'(?P<payload>.*)$'
)

NO_TS_PATTERN = re.compile(
    r'^(?P<prefix>SOC_DROP|SOC_ACCEPT|SOC_OUT): '
    r'(?P<payload>.*)$'
)

FIELD_PATTERN = re.compile(r"\b(SRC|DST|SPT|DPT|PROTO)=(\S+)")

ACTIONS = {
    "SOC_DROP": "drop",
    "SOC_ACCEPT": "accept",
    "SOC_OUT": "out",
}


def _parse_iso_timestamp(timestamp):
    """Parse ``2026-10-13T09:11:02+0000`` (short-iso) to an aware UTC dt."""
    # ``datetime.fromisoformat`` expects ``+HH:MM`` before Python 3.11, so
    # insert the missing colon when journalctl emits the compact offset.
    if re.search(r"[+-]\d{4}$", timestamp):
        timestamp = f"{timestamp[:-2]}:{timestamp[-2:]}"

    return datetime.fromisoformat(timestamp).astimezone(timezone.utc)



def _parse_fields(payload):
    fields = dict(FIELD_PATTERN.findall(payload))

    src = fields.get("SRC")
    dst = fields.get("DST")

    # A real nft log line always carries both addresses.
    if not src or not dst:
        return None

    spt = fields.get("SPT")
    dpt = fields.get("DPT")

    return {
        "src": src,
        "dst": dst,
        "spt": int(spt) if spt and spt.isdigit() else None,
        "dpt": int(dpt) if dpt and dpt.isdigit() else None,
        "proto": fields.get("PROTO"),
    }


def parse(line):
    line = line.strip()

    match = (
        LINE_PATTERN.match(line)
        or ISO_PATTERN.match(line)
        or NO_TS_PATTERN.match(line)
    )

    if not match:
        return None

    data = match.groupdict()

    fields = _parse_fields(data["payload"])

    if fields is None:
        return None

    if data.get("timestamp"):
        timestamp = data["timestamp"]

        try:
            if "T" in timestamp:
                ts_dt = _parse_iso_timestamp(timestamp)
            else:
                ts_dt = datetime.strptime(
                    f"{datetime.now(timezone.utc).year} {timestamp}",
                    "%Y %b %d %H:%M:%S",
                ).replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    else:
        ts_dt = datetime.now(timezone.utc)

    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": to_utc_iso(ts_dt),
        "host": get_hostname(),
        "log_type": "firewall",
        "category": "network",
        "action": ACTIONS[data["prefix"]],
        "src_ip": fields["src"],
        "src_port": fields["spt"],
        "dst_ip": fields["dst"],
        "dst_port": fields["dpt"],
        "user": None,
        "outcome": None,
        "details": {
            "src": fields["src"],
            "dst": fields["dst"],
            "spt": fields["spt"],
            "dpt": fields["dpt"],
            "proto": fields["proto"],
        },
        "raw": line,
    }