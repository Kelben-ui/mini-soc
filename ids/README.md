# Mini SOC IDS

Custom lightweight IDS/IPS for the Mini SOC platform. It **replaces Suricata**
(see `docs/architecture.md` §2). It runs on the single EC2 host as the
`mini-soc-ids` service (`deploy/systemd/mini-soc-ids.service`) and is
detection-only: it never changes the firewall itself. Prevention is a separate,
analyst-confirmed step (`deploy/soc-block`, task 4.7).

## Protocols monitored

| Source | How | Event |
|---|---|---|
| nftables input drops (`SOC_DROP:`) / nmap probe marker | systemd journal | Port scan (`port_scan`) |
| nftables output new connections (`SOC_OUT:`) | systemd journal | Unusual outbound (`unusual_outbound`) |
| sshd `Failed password` | systemd journal | SSH brute force (generic `ids_alert`) |
| SYN packets seen on dropped scan traffic | systemd journal | SYN flood (optional, `ids_alert`) |
| DNS queries | raw `AF_PACKET` UDP/53 sniffer | DNS anomaly (`unusual_dns`) |

The journal is read with `journalctl -f -n 0 -o short-iso`, so each event's
`raw` field keeps its original timestamp. Reading the journal needs membership
of `systemd-journal` (or `adm`); the packaged unit grants both. The DNS sniffer
needs `CAP_NET_RAW`, which the unit grants via `AmbientCapabilities` — the
service does **not** run as root.

The capture socket is opened with `AF_PACKET`/`ETH_P_ALL`, not with a
protocol-specific `ETH_P_IP`: Linux delivers outgoing frames only to packet
sockets registered for `ETH_P_ALL`, so an `ETH_P_IP` socket would see the DNS
*responses* coming back from the resolver and never the queries the daemon
exists to detect. `parse_packet()` filters the frames that do not matter
(ARP, IPv6, non-UDP, other ports). If the sniffer hits a socket error it logs
it and retries every few seconds instead of silently losing DNS detection.

## Signatures

Every signature is configurable in `ids.yaml` (`signatures:`); the defaults:

| Key | id | Message | Priority |
|---|---|---|---|
| `scan` | 9000001 | MINI-SOC Port Scan Detected | 2 |
| `ssh` | 9000002 | MINI-SOC SSH Brute Force Detected | 1 |
| `syn_flood` | 9000003 | MINI-SOC SYN Flood Detected | 2 |
| `dns` | 9000004 | MINI-SOC DNS Tunneling Suspected | 2 |
| `outbound` | 9000005 | Mini-SOC Unusual Outbound Connection | 3 |

`priority` is Suricata-style (1 = high, 2 = medium, 3 = low) and is mapped back
to `HIGH`/`MEDIUM`/`LOW` by the detection engine (contracts §3.5). Signature
`9000001` is recognized by the collector as a port scan; the DNS and outbound
signatures are carried on `dns_query` / `outbound_connection` events so they map
to `unusual_dns` / `unusual_outbound` (contracts §2.6).

Scanner user-agents (`sqlmap`, `nikto`, …) are intentionally **not** an IDS
signature here: they are detected from the nginx access log by the
`WEB-SCAN-001` detection rule.

## Output format

One JSON object per line, appended to `output.path`
(`/var/log/mini_soc_ids.json`). The shape follows contracts §2.6:

```json
{
  "timestamp": "2026-10-13T09:11:02.123456+0000",
  "event_type": "alert",
  "host": "ec2-host",
  "src_ip": "203.0.113.5",
  "src_port": 34567,
  "dest_ip": "172.31.13.199",
  "dest_port": 22,
  "proto": "TCP",
  "alert": {
    "action": "allowed",
    "gid": 1,
    "signature_id": 9000001,
    "rev": 1,
    "signature": "MINI-SOC Port Scan Detected",
    "category": "Attempted Information Leak",
    "severity": 2
  },
  "metadata": {"count": 20},
  "raw": "2026-10-13T09:11:02+0000 host kernel: SOC_DROP: ..."
}
```

DNS events add `"event_type": "dns_query"` plus
`"dns": {"qname": "...", "length": 63}`; outbound events use
`"event_type": "outbound_connection"`.

The log agent tails this file as the `mini_soc_ids` source and forwards it to
the collector, which normalizes it into the common event model.

## Configuration

`ids/ids.yaml` in the repo (`IDS_CONFIG` overrides the path). Everything is
configurable — thresholds, windows, cooldown, allow-lists, prefixes, output
path, hostname and the signature catalog. See [`ids.yaml`](ids.yaml) for the
commented full set.

```yaml
thresholds:
  scan_window_sec: 60
  scan_threshold: 20     # distinct destination ports
  ssh_window_sec: 300
  ssh_threshold: 10      # failed logins
  syn_window_sec: 60
  syn_threshold: 100     # SYN packets (optional signature)
  dns_rate_per_min: 100
  dns_max_label_len: 50
  outbound_allow: [53, 80, 443, 123]

allow_list:
  analyst_ips: []            # never alert on these
  approved_scanner_ips: []   # e.g. the approved vulnerability scanner

output:
  path: /var/log/mini_soc_ids.json

general:
  hostname: ec2-host
  soc_drop_prefix: "SOC_DROP:"
  soc_out_prefix: "SOC_OUT:"
  nmap_probe_markers: ["NMAP_SCAN_PROBE"]
  cooldown_sec: 300

dns:
  enabled: true
  interface: null   # null = all interfaces

signatures: { ... }
```

A few `IDS_*` / `SOC_HOSTNAME` variables in the repo `.env` override
individual values (systemd `EnvironmentFile`) without editing the YAML; the YAML
is the primary source.

## Running and testing

```bash
# Run as a module (repo root on sys.path):
python -m ids.live_ids_ips

# Unit tests (parse_line, thresholds, cooldown, allow-list, DNS, pruning):
pytest -v ids
```

## Files

| File | Purpose |
|---|---|
| `live_ids_ips.py` | Daemon: journal parsing, detection engine, memory pruning |
| `config.py` | `ids.yaml` loader (defaults + env overrides) |
| `dns_sniffer.py` | `AF_PACKET` UDP/53 query parser + sniffer |
| `ids.yaml` | Live configuration (also the template; `IDS_CONFIG` overrides the path) |
| `tests/test_ids.py` | Unit tests |
