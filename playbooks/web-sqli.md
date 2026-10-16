# SQL injection (`WEB-SQLI-001`)

**Severity** HIGH · **Category** web · **MITRE** T1190 · **Source** Nginx access log

> A web request whose decoded URI or body contains SQL-injection tokens.
> Determine whether the payload was only *sent* or actually *succeeded*.

## Trigger

Decoded URI/body containing SQLi tokens such as `' or `, `" or `, `union select`,
`select `, ` from `, `sleep(`, `--`, `/*`. Patterns live in `rules/sqli.yaml`.

## Triage

1. Identify the exact token that matched and the endpoint it targeted
   (commonly DVWA `/vulnerabilities/sqli/`).
2. Read the decoded URI/body from the linked event. A legitimate apostrophe in a
   form field can trip the pattern — confirm it is really an exploit attempt.
3. **Check the HTTP status and response.** A `200` that echoes database output or
   an error reveals the exploit likely **succeeded**.
4. Correlate in the last 30 minutes: the scan that found the endpoint
   (`WEB-SCAN-001`, `NET-PORTSCAN-001`) and any credential discovery
   (`WEB-BF-001`).

## Evidence

- Export the linked Nginx request events (the decoded payload is what matters).
- If exploitation looks successful, capture the **response** (not just the log
  line) and attach it to the incident.
- Record: `src_ip`, endpoint, payload, HTTP status, and whether data/execution was
  observed.

## Containment

- Isolated scanner/UA hit, no success → monitor.
- Confirmed exploitation attempt → **Block IP** for the source and promote to an
  incident.
- Evidence of success (data returned) → **Block IP** immediately, record
  **`isolate host`**, involve a lead, and treat the host as potentially compromised.

## Recovery

- Review the web root and configs for unexpected files or modifications.
- Reset the vulnerable app (DVWA) to a known-clean state.
- If credentials were exposed, rotate them.

## Closure

- Benign (own testing from an approved IP) → **FALSE POSITIVE** with a reason.
- Real attempt, no success → **RESOLVED** with a root cause (e.g. "unpatched DVWA
  `id` parameter") and lessons learned.
- Success → full incident closure, signed off by a lead.

## Related

- **Rule definition:** `rules/sqli.yaml`
- **Reproduce:** `attack-sim/sqli-xss.sh <target> sqli`
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
