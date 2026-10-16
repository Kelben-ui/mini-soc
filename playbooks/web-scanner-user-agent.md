# Scanner user-agent (`WEB-SCAN-001`)

**Severity** MEDIUM · **Category** web · **MITRE** T1595 · **Source** Nginx access log

> A request whose User-Agent names a known scanner (sqlmap, nikto, nmap,
> gobuster). Almost always reconnaissance — watch what the source does next.

## Trigger

The request's `User-Agent` contains a known scanner token. The list lives in
`rules/scanner_user_agent.yaml`.

## Triage

1. Confirm the User-Agent string and the requested path.
2. Correlate over the last 30 minutes: a scanner with **no** follow-on is often an
   authorised scan; a scanner **followed by** `WEB-SQLI-001`, `WEB-CMD-001`,
   `WEB-LFI-001` or `SSH-BF-001` from the same IP is stage 1 of an attack chain —
   promote the chain to an incident.
3. Check the source against the allow-list (analyst IP, approved scanner).

## Evidence

- Export the scanner request lines.
- Record: `src_ip`, User-Agent, requested path(s), first/last seen.

## Containment

- Standalone, low confidence → **monitor**, no block.
- Correlated with exploitation attempts → **Block IP** for the chain's source
  (1800 s is usually enough for pure recon; 3600 s if exploitation followed).

## Recovery / Closure

- Benign → **FALSE POSITIVE** with a reason.
- Part of a chain → close the alert as part of the parent incident.
- Otherwise document the UA and duration, then **RESOLVED**.

## Related

- **Rule definition:** `rules/scanner_user_agent.yaml`
- **Reproduce:** `attack-sim/scanner-ua.sh <target>`
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
