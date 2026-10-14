"""IDS configuration loader (task 4.2).

Every threshold, window, allow-list entry, output path and signature is read
from ``ids.yaml`` (installed at ``/etc/mini-soc/ids.yaml`` by
``deploy/install.sh``).  Nothing about the detector is hard-coded: if a value
is not in the file the documented default below is used, and a small set of
``IDS_*``/``SOC_HOSTNAME`` environment variables (the systemd
``EnvironmentFile``) can override individual values without editing the YAML.

Resolution order for the file itself:

1. ``$IDS_CONFIG`` when set (explicit override).
2. ``/etc/mini-soc/ids.yaml`` (production).
3. ``<repo>/ids/ids.yaml`` (local development / tests).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mini_soc_config import get_env, get_int, get_list  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SYSTEM_CONFIG_PATH = Path("/etc/mini-soc/ids.yaml")
REPO_CONFIG_PATH = REPO_ROOT / "ids" / "ids.yaml"

# Default signature catalog.  The keys are the event kinds the daemon raises;
# ``priority`` is the Suricata-style severity (1 high .. 3 low) that the
# detection engine maps back to HIGH/MEDIUM/LOW (see contracts 3.5).
SIGNATURE_DEFAULTS: dict[str, dict] = {
    "scan": {
        "id": 9000001,
        "msg": "MINI-SOC Port Scan Detected",
        "priority": 2,
        "category": "Attempted Information Leak",
    },
    "ssh": {
        "id": 9000002,
        "msg": "MINI-SOC SSH Brute Force Detected",
        "priority": 1,
        "category": "Attempted User Privilege Gain",
    },
    "syn_flood": {
        "id": 9000003,
        "msg": "MINI-SOC SYN Flood Detected",
        "priority": 2,
        "category": "Attempted Denial of Service",
    },
    "dns": {
        "id": 9000004,
        "msg": "MINI-SOC DNS Tunneling Suspected",
        "priority": 2,
        "category": "Potential DNS Tunneling",
    },
    "outbound": {
        "id": 9000005,
        "msg": "Mini-SOC Unusual Outbound Connection",
        "priority": 3,
        "category": "Potential Data Exfiltration",
    },
}


@dataclass
class IdsConfig:
    output_path: str
    hostname: str

    soc_drop_prefix: str
    soc_out_prefix: str
    nmap_probe_markers: list[str]

    scan_window_sec: int
    scan_threshold: int
    ssh_window_sec: int
    ssh_threshold: int
    syn_window_sec: int
    syn_threshold: int
    cooldown_sec: int

    dns_enabled: bool
    dns_interface: str | None
    dns_rate_per_min: int
    dns_max_label_len: int
    dns_window_sec: int

    outbound_allow: set[int]

    analyst_ips: list[str]
    approved_scanner_ips: list[str]

    journal_args: list[str]
    prune_interval_sec: int
    idle_ttl_sec: int

    signatures: dict[str, dict] = field(default_factory=dict)

    # --- Derived helpers ----------------------------------------------------
    @property
    def allowlist(self) -> set[str]:
        """Every IP that must never raise an alert (task 4.2)."""
        return set(self.analyst_ips) | set(self.approved_scanner_ips)

    def signature(self, kind: str) -> dict:
        return self.signatures.get(kind, SIGNATURE_DEFAULTS[kind])


def _resolve_path(path: str | None) -> Path:
    if path:
        return Path(path)

    env = get_env("IDS_CONFIG")
    if env:
        return Path(env)

    if SYSTEM_CONFIG_PATH.exists():
        return SYSTEM_CONFIG_PATH

    return REPO_CONFIG_PATH


def _as_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_str_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


def _as_port_set(value) -> set[int]:
    ports: set[int] = set()
    for item in _as_str_list(value):
        try:
            ports.add(int(item))
        except ValueError:
            continue
    return ports


def _merge_signatures(raw: dict) -> dict[str, dict]:
    signatures: dict[str, dict] = {}

    for kind, defaults in SIGNATURE_DEFAULTS.items():
        entry = dict(defaults)
        override = (raw.get(kind) or {}) if isinstance(raw, dict) else {}

        for key in ("id", "msg", "category"):
            if override.get(key) is not None:
                entry[key] = override[key]

        if override.get("priority") is not None:
            entry["priority"] = _as_int(
                override["priority"], defaults["priority"]
            )

        signatures[kind] = entry

    return signatures


def load_config(path: str | None = None) -> IdsConfig:
    """Load and validate the IDS configuration."""
    resolved = _resolve_path(path)

    raw: dict = {}

    if resolved.exists():
        with resolved.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}

        if not isinstance(raw, dict):
            raise ValueError(f"IDS config {resolved} must be a YAML mapping")

    thresholds = raw.get("thresholds") or {}
    allow_list = raw.get("allow_list") or {}
    output = raw.get("output") or {}
    general = raw.get("general") or {}
    dns = raw.get("dns") or {}
    signatures_raw = raw.get("signatures") or {}

    # --- Thresholds (env overrides win; YAML is the primary source) --------
    outbound_allow = thresholds.get("outbound_allow")
    if outbound_allow is None:
        outbound_allow = get_env("IDS_OUTBOUND_ALLOW")

    allowlist_env = get_list("IDS_ALLOWLIST", [])

    journal_args = general.get("journal_args") or ["-f", "-n", "0", "-o", "short-iso"]

    dns_enabled_raw = get_env("IDS_DNS_ENABLED", dns.get("enabled", True))
    dns_enabled = str(dns_enabled_raw).lower() not in {"0", "false", "no", "off"}

    analyst_ips = _as_str_list(allow_list.get("analyst_ips"))
    approved_scanner_ips = _as_str_list(allow_list.get("approved_scanner_ips"))

    # IDS_ALLOWLIST in .env is an extra suppression list, merged in here.
    for ip in allowlist_env:
        if ip not in analyst_ips and ip not in approved_scanner_ips:
            analyst_ips.append(ip)

    return IdsConfig(
        output_path=get_env("IDS_OUTPUT")
        or output.get("path")
        or "/var/log/mini_soc_ids.json",
        hostname=get_env("SOC_HOSTNAME") or general.get("hostname") or "fw-01",
        soc_drop_prefix=get_env("IDS_PREFIX_SOC_DROP")
        or general.get("soc_drop_prefix")
        or "SOC_DROP:",
        soc_out_prefix=get_env("IDS_PREFIX_SOC_OUT")
        or general.get("soc_out_prefix")
        or "SOC_OUT:",
        nmap_probe_markers=_as_str_list(
            general.get("nmap_probe_markers") or ["NMAP_SCAN_PROBE"]
        ),
        scan_window_sec=get_int(
            "IDS_SCAN_WINDOW_SEC",
            _as_int(thresholds.get("scan_window_sec"), 60),
        ),
        scan_threshold=get_int(
            "IDS_SCAN_THRESHOLD",
            _as_int(thresholds.get("scan_threshold"), 20),
        ),
        ssh_window_sec=get_int(
            "IDS_SSH_WINDOW_SEC",
            _as_int(thresholds.get("ssh_window_sec"), 300),
        ),
        ssh_threshold=get_int(
            "IDS_SSH_THRESHOLD",
            _as_int(thresholds.get("ssh_threshold"), 10),
        ),
        syn_window_sec=get_int(
            "IDS_SYN_WINDOW_SEC",
            _as_int(thresholds.get("syn_window_sec"), 60),
        ),
        syn_threshold=get_int(
            "IDS_SYN_THRESHOLD",
            _as_int(thresholds.get("syn_threshold"), 100),
        ),
        cooldown_sec=get_int(
            "IDS_COOLDOWN_SEC",
            _as_int(general.get("cooldown_sec"), 300),
        ),
        dns_enabled=dns_enabled,
        dns_interface=get_env("IDS_DNS_INTERFACE") or dns.get("interface"),
        dns_rate_per_min=get_int(
            "IDS_DNS_RATE_PER_MIN",
            _as_int(thresholds.get("dns_rate_per_min"), 100),
        ),
        dns_max_label_len=get_int(
            "IDS_DNS_MAX_LABEL",
            _as_int(thresholds.get("dns_max_label_len"), 50),
        ),
        dns_window_sec=get_int(
            "IDS_DNS_WINDOW_SEC",
            _as_int(thresholds.get("dns_window_sec"), 60),
        ),
        outbound_allow=_as_port_set(
            outbound_allow if outbound_allow is not None else [53, 80, 443, 123]
        ),
        analyst_ips=analyst_ips,
        approved_scanner_ips=approved_scanner_ips,
        journal_args=list(journal_args),
        prune_interval_sec=_as_int(general.get("prune_interval_sec"), 300),
        idle_ttl_sec=_as_int(general.get("idle_ttl_sec"), 900),
        signatures=_merge_signatures(signatures_raw),
    )
