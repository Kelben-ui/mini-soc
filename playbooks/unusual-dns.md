# Unusual DNS activity (`DNS-ANOMALY-001`)

**Severity** LOW · **Category** dns · **MITRE** T1071.004 · **Source** custom IDS (`9000004`, raw DNS sniffer)

> Over-long subdomains or a high DNS query rate — the shape of DNS tunnelling or
> exfiltration. Decide whether the host is the victim or the sender.

## Trigger

The custom IDS (`AF_PACKET` DNS sniffer) sees oversized labels (above
`IDS_DNS_MAX_LABEL`, default 50) or a high query rate from one host. Logic lives
in `rules/unusual_dns.yaml`.

## Triage

1. Check the queried name pattern (long/random labels) and the volume.
2. Determine **who is sending**: the SOC host itself (outbound exfiltration — more
   serious) or an external source (probe — usually noise).
3. Correlate with `NET-OUTBOUND-001` and web/SSH alerts — DNS tunnelling is a
   post-compromise behaviour, so it often follows a success.

## Evidence

- Export the IDS DNS events; record the query name(s), rate, and the originating
  host.

## Containment

- Host is **sending** unusual DNS → treat as suspected malware/exfiltration:
  record **`isolate host`** and investigate.
- Host is **receiving** probe-like DNS → **Block IP** if warranted.
- Known-good resolver traffic → no block; adjust the allow-list/threshold instead.

## Recovery / Closure

- Confirm queries to the suspicious domain stop after containment.
- Close as **RESOLVED**, or **FALSE POSITIVE** for approved test traffic.

## Related

- **Rule definition:** `rules/unusual_dns.yaml`
- **Reproduce:** `attack-sim/dns-tunnel-sim.sh` (run **on the instance**)
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
