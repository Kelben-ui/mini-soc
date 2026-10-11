# Mini SOC IDS

Custom lightweight IDS/IPS for the Mini SOC platform.

## Purpose
Monitors journal logs and network activity to detect:
- Port scans (SOC_DROP prefix matching)
- Outbound connections (SOC_OUT) - flags non-allowlisted ports
- DNS anomalies (long labels, high query rate)
- Additional signatures as configured

## Output
Writes alerts as JSON lines to /var/log/mini_soc_ids.json (format per contracts §2.6).

## Config
Config file: /etc/mini-soc/ids.yaml (or ids/ids.yaml). All thresholds, allow-lists, prefixes configurable.

## Service
Runs as mini-soc-ids user via systemd (mini-soc-ids.service). May require CAP_NET_RAW if sniffing DNS.
