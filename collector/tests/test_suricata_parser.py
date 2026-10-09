from collector.parsers.suricata_parser import parse


def test_suricata_alert_is_normalized():
    sample = (
        '{"timestamp":"2026-10-07T12:09:19.922763+0000",'
        '"event_type":"alert",'
        '"host":"fw-01",'
        '"src_ip":"127.0.0.1",'
        '"src_port":52820,'
        '"dest_ip":"127.0.0.1",'
        '"dest_port":1,'
        '"proto":"TCP",'
        '"alert":{'
        '"action":"allowed",'
        '"signature_id":9000001,'
        '"signature":"MINI-SOC Port Scan Detected",'
        '"category":"Attempted Information Leak",'
        '"severity":2},'
        '"metadata":{"count":20},'
        '"raw":"NMAP_SCAN_PROBE test"}'
    )

    result = parse(sample)

    assert result is not None
    assert result["event_id"]
    assert result["host"] == "fw-01"
    assert result["log_type"] == "suricata"
    assert result["category"] == "Attempted Information Leak"
    assert result["action"] == "alert"
    assert result["src_ip"] == "127.0.0.1"
    assert result["src_port"] == 52820
    assert result["dst_ip"] == "127.0.0.1"
    assert result["dst_port"] == 1
    assert result["outcome"] == "allowed"
    assert result["details"]["signature_id"] == 9000001
    assert result["details"]["severity"] == 2
    assert result["details"]["count"] == 20


def test_invalid_suricata_json_returns_none():
    result = parse("this is not json")

    assert result is None


def test_invalid_timestamp_returns_none():
    sample = (
        '{"timestamp":"test",'
        '"event_type":"alert",'
        '"host":"fw-01",'
        '"src_ip":"1.1.1.1",'
        '"raw":"manual test"}'
    )

    result = parse(sample)

    assert result is None
