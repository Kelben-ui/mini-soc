# Port scan (`NET-PORTSCAN-001`)

**Severity** MEDIUM · **Category** network · **MITRE** T1046 · **Source** custom IDS (`9000001`, from nftables `SOC_DROP:`)

> A burst of connection attempts across many destination ports from one source.
> Usually reconnaissance — the question is what follows it.

## Trigger

The custom IDS sees ≥20 distinct destination ports from one source within 60 s
(nftables `SOC_DROP:`/`SOC_ACCEPT:` lines). The normalized event drives
`rules/port_scan.yaml`.

## Triage

1. Confirm the distinct-port count and the target host.
2. Correlate over the last 30 minutes: reconnaissance with **no** follow-on is
   often an authorised scan; recon **followed by** `WEB-SQLI-001`, `WEB-CMD-001`
   or `SSH-BF-001` from the same IP is stage 1 of an attack chain — promote the
   chain to an incident.
3. Check the source against the allow-list (analyst IP, approved scanner).

## Evidence

- Export the scanned-port events.
- Record: `src_ip`, target, first/last seen, distinct port count.

## Containment

- Standalone, low confidence → **monitor**, no block.
- Correlated with exploitation attempts → **Block IP** for the chain's source
  (1800 s for pure recon; 3600 s if exploitation followed).

## Recovery / Closure

- Benign → **FALSE POSITIVE** with a reason.
- Part of a chain → close the alert within the parent incident.
- Otherwise document the ports and duration, then **RESOLVED**.

## Related

- **Rule definition:** `rules/port_scan.yaml`
- **Reproduce:** `attack-sim/port-scan.sh <target>`
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
