from collector.parsers.firewall_parser import parse
from collector.parsers.common import get_hostname

SOC_DROP = (
    "Oct 13 09:11:02 ip-172-31-13-199 kernel: SOC_DROP: IN=eth0 OUT= "
    "MAC=01:23:45:67:89:ab:cd:ef SRC=203.0.113.5 DST=172.31.13.199 "
    "LEN=60 TOS=0x00 PREC=0x00 TTL=117 ID=57626 DF PROTO=TCP "
    "SPT=34567 DPT=443 WINDOW=64240 RES=0x00 SYN URGP=0"
)

SOC_ACCEPT = (
    "Oct 13 09:12:10 ip-172-31-13-199 kernel: SOC_ACCEPT: IN=eth0 OUT= "
    "SRC=143.105.152.60 DST=172.31.13.199 LEN=52 TOS=0x00 PREC=0x00 "
    "TTL=53 ID=1234 DF PROTO=TCP SPT=52313 DPT=80 WINDOW=502 ACK URGP=0"
)

SOC_OUT = (
    "Oct 13 09:13:55 ip-172-31-13-199 kernel: SOC_OUT: IN= OUT=eth0 "
    "SRC=172.31.13.199 DST=8.8.8.8 LEN=40 TOS=0x00 PREC=0x00 TTL=64 "
    "ID=4321 DF PROTO=UDP SPT=53821 DPT=53 LEN=40"
)

# journald `-o cat` style line: no timestamp prefix.
SOC_DROP_NO_TS = (
    "SOC_DROP: IN=eth0 OUT= SRC=198.51.100.44 DST=172.31.13.199 "
    "LEN=40 TOS=0x00 TTL=52 ID=99 DF PROTO=TCP SPT=5000 DPT=22 "
    "WINDOW=64240 RES=0x00 SYN URGP=0"
)

# journald `-o short-iso` line (the log agent's firewall source, task 3.6).
SOC_DROP_SHORT_ISO = (
    "2026-10-13T09:11:02+0000 ip-172-31-13-199 kernel: SOC_DROP: IN=eth0 OUT= "
    "SRC=203.0.113.5 DST=172.31.13.199 LEN=60 TOS=0x00 PREC=0x00 TTL=117 "
    "ID=57626 DF PROTO=TCP SPT=34567 DPT=443 WINDOW=64240 RES=0x00 SYN URGP=0"
)


def test_drop_is_normalized():
    result = parse(SOC_DROP)

    assert result is not None
    assert result["log_type"] == "firewall"
    assert result["category"] == "network"
    assert result["action"] == "drop"
    assert result["src_ip"] == "203.0.113.5"
    assert result["src_port"] == 34567
    assert result["dst_ip"] == "172.31.13.199"
    assert result["dst_port"] == 443
    assert result["host"] == get_hostname()
    assert result["timestamp"].endswith("Z")
    assert result["details"] == {
        "src": "203.0.113.5",
        "dst": "172.31.13.199",
        "spt": 34567,
        "dpt": 443,
        "proto": "TCP",
    }


def test_accept_and_out_actions():
    assert parse(SOC_ACCEPT)["action"] == "accept"
    assert parse(SOC_OUT)["action"] == "out"


def test_src_dst_are_kept_for_outbound():
    result = parse(SOC_OUT)

    assert result["src_ip"] == "172.31.13.199"
    assert result["dst_ip"] == "8.8.8.8"
    assert result["details"]["dpt"] == 53


def test_journald_cat_line_without_timestamp_parses():
    result = parse(SOC_DROP_NO_TS)

    assert result is not None
    assert result["action"] == "drop"
    assert result["dst_ip"] == "172.31.13.199"
    assert result["timestamp"].endswith("Z")


def test_journald_short_iso_line_parses():
    result = parse(SOC_DROP_SHORT_ISO)

    assert result is not None
    assert result["action"] == "drop"
    assert result["src_ip"] == "203.0.113.5"
    assert result["src_port"] == 34567
    assert result["dst_port"] == 443
    assert result["timestamp"] == "2026-10-13T09:11:02Z"


def test_malformed_lines_return_none():
    assert parse("random kernel line") is None
    assert parse("") is None
    assert parse("SOC_DROP: IN=eth0") is None  # missing SRC/DST
    assert parse(
        "Oct 13 09:11:02 host kernel: SOC_MISS: SRC=1.2.3.4 DST=5.6.7.8"
    ) is None