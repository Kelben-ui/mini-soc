"""Unit tests for the Mini SOC IDS (task 4.10).

Fed fake journal lines and synthetic DNS frames, these cover ``parse_line``,
the thresholds, the cooldown, the allow-list, the optional SYN-flood
signature, DNS anomaly detection, memory pruning and the sniffer parser.
"""

import copy
import json
import os
import struct

import pytest

from ids.config import load_config
from ids.dns_sniffer import parse_dns_query, parse_packet
from ids.live_ids_ips import IdsEngine, parse_line


DROP = (
    "2026-10-13T09:11:02+0000 ip-172-31-13-199 kernel: "
    "SOC_DROP: IN=eth0 OUT= SRC=203.0.113.5 DST=172.31.13.199 "
    "LEN=60 PROTO=TCP SPT=34567 DPT=4321 SYN URGP=0"
)

DROP_NMAP = (
    "SOC_DROP: IN=eth0 OUT= SRC=203.0.113.9 DST=172.31.13.199 "
    "PROTO=TCP SPT=40000 DPT=7 SYN"
)

OUT = (
    "2026-10-13T09:13:55+0000 ip-172-31-13-199 kernel: "
    "SOC_OUT: IN= OUT=eth0 SRC=172.31.13.199 DST=198.51.100.9 "
    "LEN=60 PROTO=TCP SPT=51000 DPT=4444 SYN"
)

SSH = (
    "2026-10-13T09:12:00+0000 ip-172-31-13-199 sshd[123]: "
    "Failed password for invalid user root from 198.51.100.7 port 55000 ssh2"
)

BASE = {
    "thresholds": {
        "scan_window_sec": 60,
        "scan_threshold": 5,
        "ssh_window_sec": 300,
        "ssh_threshold": 3,
        "syn_window_sec": 60,
        "syn_threshold": 100,
        "dns_rate_per_min": 100,
        "dns_max_label_len": 50,
        "outbound_allow": [53, 80, 443, 123],
    },
    "allow_list": {"analyst_ips": [], "approved_scanner_ips": []},
    "output": {"path": "unused.json"},
    "general": {
        "hostname": "test-host",
        "soc_drop_prefix": "SOC_DROP:",
        "soc_out_prefix": "SOC_OUT:",
        "nmap_probe_markers": ["NMAP_SCAN_PROBE"],
        "cooldown_sec": 300,
        "journal_args": ["-f", "-n", "0", "-o", "short-iso"],
        "prune_interval_sec": 300,
        "idle_ttl_sec": 900,
    },
    "dns": {"enabled": False, "interface": None},
}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Stop /etc/mini-soc/.env or the repo .env from overriding test values."""
    for name in list(os.environ):
        if name.startswith("IDS_") or name in {"SOC_HOSTNAME", "IDS_CONFIG"}:
            monkeypatch.delenv(name, raising=False)


def _write_config(tmp_path, **overrides):
    data = copy.deepcopy(BASE)

    for section, values in overrides.items():
        data.setdefault(section, {}).update(values)

    path = tmp_path / "ids.yaml"

    # YAML is a superset of JSON, so JSON dumps is a valid stand-in here.
    path.write_text(json.dumps(data), encoding="utf-8")

    return load_config(str(path))


def make_config(tmp_path, **overrides):
    config = _write_config(tmp_path, **overrides)
    config.output_path = str(tmp_path / "alerts.json")
    return config


def read_events(config):
    try:
        with open(config.output_path) as handle:
            return [json.loads(line) for line in handle if line.strip()]
    except FileNotFoundError:
        return []


# --- parse_line -------------------------------------------------------------


def test_parse_line_scan_short_iso(tmp_path):
    info = parse_line(DROP, make_config(tmp_path))

    assert info["kind"] == "scan"
    assert info["src_ip"] == "203.0.113.5"
    assert info["dest_port"] == 4321
    assert info["proto"] == "TCP"
    assert info["syn"] is True


def test_parse_line_nmap_probe_marker(tmp_path):
    info = parse_line(DROP_NMAP, make_config(tmp_path))

    assert info["kind"] == "scan"
    assert info["dest_port"] == 7


def test_parse_line_outbound(tmp_path):
    info = parse_line(OUT, make_config(tmp_path))

    assert info["kind"] == "outbound"
    assert info["dest_port"] == 4444
    assert info["dest_ip"] == "198.51.100.9"


def test_parse_line_ssh(tmp_path):
    info = parse_line(SSH, make_config(tmp_path))

    assert info["kind"] == "ssh"
    assert info["src_ip"] == "198.51.100.7"
    assert info["dest_port"] == 22


def test_parse_line_ignores_unrelated(tmp_path):
    assert parse_line("just a normal log line", make_config(tmp_path)) is None


def test_prefix_is_configurable(tmp_path):
    config = make_config(
        tmp_path, general={"soc_drop_prefix": "FW-DROP:"}
    )

    assert parse_line(DROP, config) is None

    custom = DROP.replace("SOC_DROP:", "FW-DROP:")

    assert parse_line(custom, config)["kind"] == "scan"


# --- thresholds + cooldown --------------------------------------------------


def test_scan_threshold(tmp_path):
    config = make_config(tmp_path)
    engine = IdsEngine(config)
    now = 1_000_000.0

    for port in range(1, 5):
        line = DROP.replace("DPT=4321", f"DPT={port}")
        assert engine.process_line(line, now=now) == []

    fifth = DROP.replace("DPT=4321", "DPT=5555")
    events = engine.process_line(fifth, now=now)

    assert len(events) == 1
    assert events[0]["alert"]["signature_id"] == 9000001
    assert events[0]["metadata"]["count"] == 5


def test_scan_cooldown(tmp_path):
    config = make_config(tmp_path, general={"cooldown_sec": 300})
    engine = IdsEngine(config)
    now = 1_000_000.0

    for port in range(1, 6):
        engine.process_line(DROP.replace("DPT=4321", f"DPT={port}"), now=now)

    assert len(read_events(config)) == 1

    # Another burst inside the cooldown window must not alert again.
    for port in range(6, 11):
        engine.process_line(DROP.replace("DPT=4321", f"DPT={port}"), now=now + 10)

    assert len(read_events(config)) == 1

    # After the cooldown a fresh burst alerts again.
    for port in range(20, 25):
        engine.process_line(
            DROP.replace("DPT=4321", f"DPT={port}"), now=now + 400
        )

    assert len(read_events(config)) == 2


def test_ssh_threshold(tmp_path):
    config = make_config(tmp_path)
    engine = IdsEngine(config)
    now = 1_000_000.0

    for index in range(2):
        assert engine.process_line(SSH, now=now + index) == []

    events = engine.process_line(SSH, now=now + 2)

    assert len(events) == 1
    assert events[0]["alert"]["signature_id"] == 9000002


# --- allow-list -------------------------------------------------------------


def test_allowlisted_ip_is_ignored(tmp_path):
    config = make_config(
        tmp_path, allow_list={"approved_scanner_ips": ["203.0.113.5"]}
    )
    engine = IdsEngine(config)
    now = 1_000_000.0

    for port in range(1, 8):
        assert engine.process_line(DROP.replace("DPT=4321", f"DPT={port}"), now=now) == []

    assert read_events(config) == []


# --- outbound ---------------------------------------------------------------


def test_outbound_allowlisted_port_is_silent(tmp_path):
    config = make_config(tmp_path)
    engine = IdsEngine(config)

    assert engine.process_line(OUT.replace("DPT=4444", "DPT=443"), now=1.0) == []
    assert read_events(config) == []


def test_outbound_unusual_port_alerts(tmp_path):
    config = make_config(tmp_path)
    engine = IdsEngine(config)

    events = engine.process_line(OUT, now=1.0)

    assert len(events) == 1
    assert events[0]["event_type"] == "outbound_connection"
    assert events[0]["alert"]["signature_id"] == 9000005
    assert events[0]["dest_port"] == 4444


# --- SYN flood (4.6) --------------------------------------------------------


def test_syn_flood_signature(tmp_path):
    config = make_config(tmp_path, thresholds={"syn_threshold": 3})
    engine = IdsEngine(config)
    now = 1_000_000.0

    # Only count, do not cross the scan threshold: reuse one port.
    for index in range(2):
        engine.process_line(DROP.replace("DPT=4321", "DPT=80"), now=now + index)

    events = engine.process_line(DROP.replace("DPT=4321", "DPT=80"), now=now + 2)
    kinds = {event["alert"]["signature_id"] for event in events}

    assert 9000003 in kinds


# --- DNS (4.5) --------------------------------------------------------------


def test_dns_long_label_alerts(tmp_path):
    config = make_config(tmp_path)
    engine = IdsEngine(config)

    long_label = "a" * 60 + ".example.com"
    events = engine.process_dns(long_label, "172.31.13.199", now=1.0)

    assert len(events) == 1
    assert events[0]["event_type"] == "dns_query"
    assert events[0]["alert"]["signature_id"] == 9000004
    assert events[0]["dns"]["qname"] == long_label


def test_dns_rate_alerts(tmp_path):
    config = make_config(tmp_path)
    engine = IdsEngine(config)

    for index in range(100):
        engine.process_dns(f"q{index}.example.com", "172.31.13.199", now=1000.0)

    assert read_events(config) == []

    events = engine.process_dns("q101.example.com", "172.31.13.199", now=1000.0)

    assert len(events) == 1
    assert events[0]["event_type"] == "dns_query"


def test_dns_allowlisted_source_ignored(tmp_path):
    config = make_config(
        tmp_path, allow_list={"analyst_ips": ["172.31.13.199"]}
    )
    engine = IdsEngine(config)

    assert engine.process_dns("a" * 60 + ".example.com", "172.31.13.199") == []


# --- memory pruning (4.8) ---------------------------------------------------


def test_prune_removes_idle_ips(tmp_path):
    config = make_config(tmp_path)
    engine = IdsEngine(config)
    now = 1_000_000.0

    for port in range(1, 3):
        engine.process_line(DROP.replace("DPT=4321", f"DPT={port}"), now=now)

    assert "203.0.113.5" in engine.scan_hits
    engine.last_alert[("203.0.113.5", "scan")] = now

    engine._prune(now + 10_000)

    assert engine.scan_hits == {}
    assert engine.last_alert == {}


# --- DNS packet parser ------------------------------------------------------

def _dns_query_payload(qname):
    parts = b""

    for label in qname.split("."):
        parts += bytes([len(label)]) + label.encode()

    parts += b"\x00"

    header = struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)

    return header + parts + struct.pack("!HH", 1, 1)


def _udp_ipv4_frame(qname, dport=53):
    payload = _dns_query_payload(qname)

    udp = struct.pack("!HHHH", 51000, dport, 8 + len(payload), 0) + payload

    total_len = 20 + len(udp)
    ip = struct.pack(
        "!BBHHHBBH4s4s",
        0x45,
        0,
        total_len,
        0,
        0,
        64,
        17,
        0,
        b"\xac\x1f\x0d\xc7",  # 172.31.13.199
        b"\xc0\x00\x02\x09",  # 192.0.2.9
    )

    ethernet = b"\x00" * 12 + struct.pack("!H", 0x0800)

    return ethernet + ip + udp


def test_parse_dns_query_payload():
    assert parse_dns_query(_dns_query_payload("tunnel.example.com")) == (
        "tunnel.example.com"
    )


def test_parse_packet_extracts_qname():
    packet = parse_packet(_udp_ipv4_frame("tunnel.example.com"))

    assert packet["qname"] == "tunnel.example.com"
    assert packet["src_ip"] == "172.31.13.199"
    assert packet["dport"] == 53


def test_parse_packet_ignores_other_ports():
    frame = _udp_ipv4_frame("tunnel.example.com", dport=1234)  # NTP, not DNS

    assert parse_packet(frame) is None


# --- output feeds the collector contract (4.3 / 4.11) -----------------------


def test_events_feed_the_collector_contract(tmp_path):
    """Every event the IDS writes normalizes to the documented rule inputs."""
    from collector.parsers.suricata_parser import parse

    config = make_config(tmp_path)
    engine = IdsEngine(config)

    outbound = engine.process_line(OUT, now=1.0)[0]
    mapped = parse(json.dumps(outbound), log_type="mini_soc_ids")

    assert (mapped["category"], mapped["action"]) == (
        "network",
        "unusual_outbound",
    )

    dns = engine.process_dns("a" * 60 + ".example.com", "172.31.13.199", now=1.0)[0]
    mapped = parse(json.dumps(dns), log_type="mini_soc_ids")

    assert (mapped["category"], mapped["action"]) == ("dns", "unusual_dns")

    for port in range(1, 6):
        events = engine.process_line(
            DROP.replace("DPT=4321", f"DPT={port}"), now=100.0
        )

    assert len(events) == 1
    mapped = parse(json.dumps(events[0]), log_type="mini_soc_ids")

    assert (mapped["category"], mapped["action"]) == ("network", "port_scan")
    assert mapped["details"]["signature_id"] == 9000001
    assert mapped["details"]["count"] == 5

