"""Shared helpers for collector parsers.

Provides the real hostname, the instance private IP, and UTC timestamp
normalization required by the frozen event contract (docs/contracts.md §2.5):

- ``host`` must be the real hostname of the collector instance.
- ``dst_ip`` must be the collector instance private IP for local services.
- Timestamps must be normalized to UTC.
"""

import os
import socket
from datetime import datetime, timezone


def get_hostname():
    """Real hostname of the collector instance (env override supported)."""
    return os.getenv("SOC_HOSTNAME") or socket.gethostname()


def get_private_ip():
    """Instance private IP used as dst_ip for local services.

    Override with SOC_PRIVATE_IP; otherwise auto-detect and fall back to
    127.0.0.1.
    """
    override = os.getenv("SOC_PRIVATE_IP")

    if override:
        return override

    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "127.0.0.1"


def to_utc_iso(dt):
    """Normalize a datetime to UTC and return ISO-8601 with a ``Z`` suffix.

    Naive datetimes are assumed to already be UTC.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return (
        dt.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )