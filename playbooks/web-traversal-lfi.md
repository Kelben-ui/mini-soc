# Directory traversal / LFI (`WEB-LFI-001`)

**Severity** HIGH · **Category** web · **MITRE** T1083 · **Source** Nginx access log

> A web request that tries to read files outside the web root (`../`,
> `/etc/passwd`, `php://`). Confirm whether a file was actually disclosed.

## Trigger

Decoded URI/body containing `../`, `/etc/passwd`, or `php://`. Patterns live in
`rules/traversal_lfi.yaml`.

## Triage

1. Identify the parameter and the path being requested.
2. Read the decoded URI/body from the linked event.
3. Check the response for file **contents** (e.g. a `root:x:0:0:` passwd line) —
   that proves disclosure.
4. Correlate with `WEB-SCAN-001` / `NET-PORTSCAN-001` and the other web rules.

## Evidence

- Export the linked Nginx request events.
- If contents appear in the response, capture the response body and attach it.
- Record: `src_ip`, endpoint, parameter, requested path, and whether data was
  returned.

## Containment

- Isolated probe, no disclosure → monitor.
- Confirmed disclosure or part of an active chain → **Block IP** for the source and
  promote to an incident.
- If sensitive files were read, record **`isolate host`** and rotate any secrets
  they exposed.

## Recovery

- Review the web root and configs for unexpected files or modifications.
- Reset DVWA to a known-clean state.
- Rotate any credentials or keys the disclosed files could have contained.

## Closure

- Benign (approved test) → **FALSE POSITIVE** with a reason.
- Real attempt, no disclosure → **RESOLVED** with root cause and lessons learned.
- Disclosure → full incident closure.

## Related

- **Rule definition:** `rules/traversal_lfi.yaml`
- **Reproduce:** `attack-sim/sqli-xss.sh <target> traversal`
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
