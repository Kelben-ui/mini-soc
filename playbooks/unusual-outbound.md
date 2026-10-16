# Unusual outbound connection (`NET-OUTBOUND-001`)

**Severity** MEDIUM · **Category** network · **MITRE** T1041 · **Source** custom IDS (`9000005`, from nftables `SOC_OUT:`)

> The host opened an outbound connection to a port outside the allow-list
> (53/80/443/123). Could be a mis-configured service — or command-and-control.

## Trigger

The custom IDS sees the host open a connection to a non-allow-listed destination
port (from the nftables `SOC_OUT:` journal line). Logic lives in
`rules/unusual_outbound.yaml`.

## Triage

1. Identify the destination IP/port and the **process** that opened it
   (`ss -tnp`, `lsof -i`).
2. Decide whether it is legitimate egress the allow-list should cover, a
   mis-configured service, or C2/exfiltration.
3. Correlate with `DNS-ANOMALY-001`, `SSH-SUCCESS-001`, or a recent web
   exploitation — outbound traffic is a classic post-compromise signal.

## Evidence

- Export the `SOC_OUT:` events; record `dst_ip`, `dst_port`, and the owning
  process.

## Containment

- Known-good service → update the egress allow-list (do **not** block).
- Suspicious/unexplained → **Block IP** the destination and record
  **`isolate host`** pending investigation.

## Recovery / Closure

- Confirm no further connections to the destination after the block.
- Document the root cause; close **RESOLVED** (or **FALSE POSITIVE** for
  legitimate traffic).

## Related

- **Rule definition:** `rules/unusual_outbound.yaml`
- **Reproduce:** `attack-sim/outbound-conn.sh 203.0.113.5 4444` (run **on the instance**)
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
