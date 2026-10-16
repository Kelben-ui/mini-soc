# Command injection (`WEB-CMD-001`)

**Severity** HIGH · **Category** web · **MITRE** T1059 · **Source** Nginx access log

> A web request that appends OS commands to a parameter. If it executed, an
> attacker has shell-equivalent access to the host — treat as critical.

## Trigger

Decoded URI/body containing shell separators followed by commands: `; id`,
`; whoami`, `| id`, `| whoami`, `&& id`, `&& whoami`. Patterns live in
`rules/command_injection.yaml`.

## Triage

1. Identify the parameter and the exact command appended.
2. Read the decoded URI/body from the linked event.
3. Check the response for command **output** (`uid=...`, a username) — that proves
   execution, not just an attempt.
4. Correlate with the scanner and web rules in the last 30 minutes.

## Evidence

- Export the linked Nginx request events.
- Capture the response body if it appears to contain command output, and attach it.
- Record: `src_ip`, endpoint, parameter, the injected command, and whether output
  was observed.

## Containment

- Confirmed/plausible execution → **Block IP** immediately, record **`isolate
  host`**, and involve a lead.
- There is no container to stop — this is a **host-level** review of `soc-01`.

## Recovery

- Look for the commands' side effects: new files, users, cron jobs, reverse shells,
  modified configs.
- If execution is confirmed, rebuild from the clean-baseline AMI rather than
  cleaning in place.
- Reset DVWA to a clean state.

## Closure

- Benign (approved test) → **FALSE POSITIVE** with a reason.
- Real attempt, no execution → **RESOLVED** with root cause and lessons learned.
- Execution → full incident closure signed off by a lead.

## Related

- **Rule definition:** `rules/command_injection.yaml`
- **Reproduce:** `attack-sim/sqli-xss.sh <target> cmdi`
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
