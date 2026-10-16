# Cross-site scripting (`WEB-XSS-001`)

**Severity** MEDIUM · **Category** web · **MITRE** T1059 · **Source** Nginx access log

> A web request whose decoded URI or body contains XSS tokens. Usually an
> automated probe; confirm whether the payload was reflected.

## Trigger

Decoded URI/body containing `<script`, `javascript:`, `onerror=`, `onload=`.
Patterns live in `rules/xss.yaml`.

## Triage

1. Identify the token and the endpoint/parameter it was sent to.
2. Read the decoded URI/body from the linked event to confirm it is a payload and
   not a benign string (a legitimate `<script>` in documentation, for example).
3. Check whether the response **reflected** the payload unencoded — that is what
   turns a probe into a real finding.
4. Correlate with `WEB-SCAN-001` / `NET-PORTSCAN-001` (the scan that found the
   endpoint) and other web rules in the last 30 minutes.

## Evidence

- Export the linked Nginx request events with the decoded payload.
- If reflection is suspected, capture the response and attach it to the incident.
- Record: `src_ip`, endpoint, parameter, payload, and whether it was reflected.

## Containment

- Isolated probe, no reflection → monitor.
- Reflected/stored payload or part of an active chain → **Block IP** for the source
  and promote to an incident.
- If the payload was **stored** server-side, treat like code execution: record
  **`isolate host`** and involve a lead.

## Recovery

- Confirm the vulnerable endpoint now encodes output; reset DVWA to a clean state.
- Check stored pages (guestbooks, profiles) for persisted payloads.

## Closure

- Benign (approved test traffic) → **FALSE POSITIVE** with a reason.
- Real attempt, not reflected → **RESOLVED** with root cause and lessons learned.
- Reflected/stored → full incident closure.

## Related

- **Rule definition:** `rules/xss.yaml`
- **Reproduce:** `attack-sim/sqli-xss.sh <target> xss`
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
