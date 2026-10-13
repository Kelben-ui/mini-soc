import json

from collector.parsers.suricata_parser import parse

PORT_SCAN = {
    "timestamp": "2026-10-07T12:09:19.922763+0000",
    "event_type": "alert",
    "host": "fw-01",
    "src_ip": "127.0.0.1",
    "src_port": 52820,
    "dest_ip": "127.0.0.1",
    "dest_port": 1,
    "proto": "TCP",
    "alert": {
        "action": "allowed",
        "signature_id": 9000001,
        "signature": "MINI-SOC Port Scan Detected",
        "category": "Attempted Information Leak",
        "severity": 2,
    },
    "metadata": {"count": 20},
    "raw": "NMAP_SCAN_PROBE test",
}

SSH_BF = {
    "timestamp": "2026-10-07T12:20:00.000000Z",
    "event_type": "alert",
    "src_ip": "203.0.113.9",
    "src_port": 52820,
    "dest_ip": "172.31.13.199",
    "dest_port": 22,
    "proto": "TCP",
    "alert": {
        "action": "blocked",
        "signature_id": 9000002,
        "signature": "MINI-SOC SSH Brute Force Detected",
        "category": "Attempted User Privilege Gain",
        "severity": 1,
    },
    "metadata": {"count": 15},
}

DNS_QUERY = {
    "timestamp": "2026-10-07T12:30:00.000000+0000",
    "event_type": "dns_query",
    "src_ip": "10.0.0.5",
    "dest_ip": "8.8.8.8",
    "dest_port": 53,
    "proto": "UDP",
    "dns": {"qname": "evil.example.com"},
}

OUTBOUND = {
    "timestamp": "2026-10-07T12:40:00.000000+0000",
    "event_type": "outbound_connection",
    "src_ip": "172.31.13.199",
    "dest_ip": "198.51.100.200",
    "dest_port": 4444,
    "proto": "TCP",
}


def _line(payload):
    return json.dumps(payload)


def test_port_scan_signature_becomes_network_port_scan():
    result = parse(_line(PORT_SCAN), log_type="mini_soc_ids")

    assert result is not None
    assert result["log_type"] == "mini_soc_ids"
    assert result["category"] == "network"
    assert result["action"] == "port_scan"
    assert result["details"] == {
        "signature_id": 9000001,
        "signature": "MINI-SOC Port Scan Detected",
        "priority": 2,
        "count": 20,
    }
    assert result["timestamp"].endswith("Z")
    assert result["src_port"] == 52820
    assert result["dst_port"] == 1


def test_generic_ids_alert_keeps_ids_ids_alert():
    result = parse(_line(SSH_BF))

    assert result["category"] == "ids"
    assert result["action"] == "ids_alert"
    assert result["details"]["priority"] == 1
    assert result["details"]["signature_id"] == 9000002


def test_dns_event_becomes_dns_unusual_dns():
    result = parse(_line(DNS_QUERY))

    assert result["category"] == "dns"
    assert result["action"] == "unusual_dns"


def test_outbound_event_becomes_network_unusual_outbound():
    result = parse(_line(OUTBOUND))

    assert result["category"] == "network"
    assert result["action"] == "unusual_outbound"


def test_ports_are_validated():
    bad_port = dict(PORT_SCAN)
    bad_port["src_port"] = -1
    bad_port["dest_port"] = 99999

    result = parse(_line(bad_port))

    assert result["src_port"] is None
    assert result["dst_port"] is None


def test_malformed_lines_return_none():
    assert parse("not json at all") is None
    assert parse("") is None
    assert parse(_line({"event_type": "alert"})) is None  # no timestamp
    assert parse(
        _line({"timestamp": "not-a-date", "event_type": "alert"})
    ) is None