"""Generate lab sample logs for all 13 detection rules.

The EC2 box is currently unreachable, so these lines are hand-built to be
byte-format-identical to the real sources:

- nginx_access:  deploy/nginx/mini-soc.conf `soc` log format
- auth:          rsyslog auth.log (syslog prefix)
- mini_soc_ids:  ids/live_ids_ips.py JSON output
- firewall:      kern.log nftables log lines (SOC_DROP/SOC_ACCEPT/SOC_OUT)

All timestamps sit inside a single 300s window (2026-10-13 09:15:00Z ..
09:19:59Z) so the whole dataset can be replayed through the detection engine
in one shot and every rule's threshold window is satisfied.

Run:  python sample-data/generate.py
"""

from pathlib import Path

BASE = Path(__file__).resolve().parent

HOST = "ip-172-31-13-199"
ATTACKER = "203.0.113.9"
SCANNER = "203.0.113.5"
FLOODER = "198.51.100.44"
BRUTER = "203.0.113.7"
ANALYST = "143.105.152.60"

# ---------------------------------------------------------------- nginx access
SOC = (
    '{ip} - - [iso={ts}] '
    '"{method} {target} HTTP/1.1" {status} {bytes} '
    '"{referer}" "{ua}" body={body}'
)


def nginx_lines():
    lines = []

    # WEB-SQLI-001 (%27+OR+1%3D1 -> "id=' OR 1=1" after decoding)
    lines.append(SOC.format(
        ip=SCANNER,
        ts="2026-10-13T09:15:00+00:00",
        method="GET",
        target="/vulnerabilities/sqli/?id=%27+OR+1%3D1",
        status=200,
        bytes=1450,
        referer="-",
        ua="sqlmap/1.8",
        body="",
    ))

    # WEB-XSS-001
    lines.append(SOC.format(
        ip=SCANNER,
        ts="2026-10-13T09:15:03+00:00",
        method="GET",
        target="/vulnerabilities/xss/?name=%3Cscript%3Ealert(1)%3C%2Fscript%3E",
        status=200,
        bytes=1337,
        referer="-",
        ua="sqlmap/1.8",
        body="",
    ))

    # WEB-CMD-001
    lines.append(SOC.format(
        ip=SCANNER,
        ts="2026-10-13T09:15:06+00:00",
        method="GET",
        target="/vulnerabilities/exec/?ip=127.0.0.1%3B+whoami",
        status=200,
        bytes=700,
        referer="-",
        ua="sqlmap/1.8",
        body="",
    ))

    # WEB-LFI-001
    lines.append(SOC.format(
        ip=SCANNER,
        ts="2026-10-13T09:15:09+00:00",
        method="GET",
        target="/vulnerabilities/fi/?page=..%2F..%2F..%2Fetc%2Fpasswd",
        status=200,
        bytes=900,
        referer="-",
        ua="sqlmap/1.8",
        body="",
    ))

    # WEB-SCAN-001 (scanner user agent)
    lines.append(SOC.format(
        ip=SCANNER,
        ts="2026-10-13T09:15:12+00:00",
        method="GET",
        target="/",
        status=200,
        bytes=3120,
        referer="-",
        ua="sqlmap/1.8#stable",
        body="",
    ))

    # WEB-BF-001: 20x POST /dvwa/login.php 401 from one src inside the 120s window.
    for i in range(20):
        lines.append(SOC.format(
            ip=BRUTER,
            ts=f"2026-10-13T09:16:{i:02d}+00:00",
            method="POST",
            target="/dvwa/login.php",
            status=401,
            bytes=512,
            referer="http://127.0.0.1/dvwa/login.php",
            ua="curl/8.0",
            body="username=admin&password=guess01",
        ))

    # WEB-FLOOD-001: 301 requests with status 301 (config count=301/60s).
    for i in range(301):
        lines.append(SOC.format(
            ip=FLOODER,
            ts=f"2026-10-13T09:19:{min(i // 5, 59):02d}+00:00",
            method="GET",
            target=f"/page?n={i}",
            status=301,
            bytes=178,
            referer="-",
            ua="ab/1.0",
            body="",
        ))

    return lines


# ---------------------------------------------------------------- nginx error
def nginx_error_lines():
    return [
        "2026/10/13 09:15:40 [error] 37677#0: *3 "
        "connect() failed (111: Connection refused) while connecting to "
        "upstream, client: 203.0.113.5, server: _, request: \"GET / HTTP/1.1\", "
        "upstream: \"http://127.0.0.1:8000/\"",

        "2026/10/13 09:15:41 [crit] 37677#0: *9 "
        "open() \"/opt/mini-soc/frontend/dist/nope\" failed "
        "(2: No such file or directory), client: 198.51.100.44, server: _, "
        "request: \"GET /nope HTTP/1.1\"",

        "2026/10/13 09:15:42 [warn] 37677#0: *12 "
        "an upstream response is buffered to a temporary file",
    ]


# ---------------------------------------------------------------- auth.log
def auth_lines():
    lines = []

    # SSH-BF-001: 12 failed logins from one src inside the 300s window.
    for i in range(12):
        lines.append(
            f"Oct 13 09:17:{i:02d} {HOST} sshd[2203]: "
            f"Failed password for root from {ATTACKER} port 5282{i} ssh2"
        )

    # SSH-SUCCESS-001: accept of the brute-forcing source right after.
    lines.append(
        f"Oct 13 09:17:30 {HOST} sshd[2261]: Accepted password for "
        f"ubuntu from {ATTACKER} port 52821 ssh2"
    )

    # A legitimate analyst login (must NOT fire SSH-SUCCESS-001).
    lines.append(
        f"Oct 13 09:17:31 {HOST} sshd[2261]: Accepted publickey for "
        f"ubuntu from {ANALYST} port 52313 ssh2: RSA SHA256:abcd"
    )

    lines.append(
        f"Oct 13 09:17:25 {HOST} sshd[2289]: Invalid user guest "
        f"from {ATTACKER} port 53777"
    )

    lines.append(
        f"Oct 13 09:17:40 {HOST} sudo: pam_unix(sudo:session): "
        "session opened for user root by (uid=0)"
    )

    return lines


# ---------------------------------------------------------------- mini_soc_ids
def ids_lines():
    return [
        # NET-PORTSCAN-001
        '{"timestamp":"2026-10-13T09:18:00.922763+0000",'
        '"event_type":"alert","src_ip":"' + SCANNER + '",'
        '"src_port":52820,"dest_ip":"172.31.13.199","dest_port":1,'
        '"proto":"TCP","alert":{"action":"allowed","signature_id":9000001,'
        '"signature":"MINI-SOC Port Scan Detected",'
        '"category":"Attempted Information Leak","severity":2},'
        '"metadata":{"count":20},"raw":"NMAP_SCAN_PROBE test"}',

        # IDS-SIG-001
        '{"timestamp":"2026-10-13T09:18:05.000000+0000",'
        '"event_type":"alert","src_ip":"' + ATTACKER + '",'
        '"src_port":52820,"dest_ip":"172.31.13.199","dest_port":22,'
        '"proto":"TCP","alert":{"action":"blocked","signature_id":9000002,'
        '"signature":"MINI-SOC SSH Brute Force Detected",'
        '"category":"Attempted User Privilege Gain","severity":1},'
        '"metadata":{"count":15}}',

        # DNS-ANOMALY-001
        '{"timestamp":"2026-10-13T09:18:10.000000+0000",'
        '"event_type":"dns_query","src_ip":"172.31.13.199",'
        '"dest_ip":"8.8.8.8","dest_port":53,"proto":"UDP",'
        '"dns":{"qname":"' + ("x" * 60) + '.example.com"}}',

        # NET-OUTBOUND-001
        '{"timestamp":"2026-10-13T09:18:15.000000+0000",'
        '"event_type":"outbound_connection","src_ip":"172.31.13.199",'
        '"dest_ip":"198.51.100.200","dest_port":4444,"proto":"TCP"}',
    ]


# ---------------------------------------------------------------- firewall
def firewall_lines():
    return [
        # SOC_DROP (source: nftables.conf `log prefix "SOC_DROP: " drop`)
        f"Oct 13 09:18:30 {HOST} kernel: SOC_DROP: IN=eth0 OUT= "
        f"MAC=01:23:45:67:89:ab:cd:ef SRC={SCANNER} DST=172.31.13.199 "
        "LEN=60 TOS=0x00 PREC=0x00 TTL=117 ID=57626 DF PROTO=TCP "
        "SPT=34567 DPT=443 WINDOW=64240 RES=0x00 SYN URGP=0",

        f"Oct 13 09:18:31 {HOST} kernel: SOC_ACCEPT: IN=eth0 OUT= "
        f"SRC={ANALYST} DST=172.31.13.199 LEN=52 TOS=0x00 TTL=53 "
        "ID=1234 DF PROTO=TCP SPT=52313 DPT=80 WINDOW=502 ACK URGP=0",

        f"Oct 13 09:18:32 {HOST} kernel: SOC_OUT: IN= OUT=eth0 "
        "SRC=172.31.13.199 DST=8.8.8.8 LEN=40 TOS=0x00 TTL=64 "
        "ID=4321 DF PROTO=UDP SPT=53821 DPT=53 LEN=40",
    ]


def write_file(name, lines):
    target = BASE / name
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {name} ({len(lines)} lines)")


def main():
    write_file("nginx_access.log", nginx_lines())
    write_file("nginx_error.log", nginx_error_lines())
    write_file("auth.log", auth_lines())
    write_file("mini_soc_ids.json", ids_lines())
    write_file("firewall_kern.log", firewall_lines())


if __name__ == "__main__":
    main()