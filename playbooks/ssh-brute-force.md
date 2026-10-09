# Playbook: SSH Brute Force

## Trigger
Rule: SSH brute force — ≥10 failed logins from the same src_ip against the
same dst_ip within 5 minutes, sourced from auth.log. Severity: HIGH.

Related rule: Login success after brute force — a successful login from an
IP with an open brute-force alert. Severity: CRITICAL.

[FILL IN: confirm your custom IDS parses auth.log itself, or whether it
consumes events already normalized by the collector. If your IDS does its
own auth.log parsing independent of the collector's `ssh_login` events,
note the difference here so triage steps below match reality.]

## Triage
1. Confirm the alert: ≥10 failed SSH logins, same src_ip → same dst_ip,
   within 5 minutes.
2. Check whether a SUCCESS followed the failures on the same src_ip —
   if so, this is now CRITICAL (a compromised credential is in use), not
   just an ongoing attempt. Escalate immediately.
3. Identify the target account(s) being tried — is it one account
   (targeted) or several (spraying)?
4. Check if this src_ip triggers other alerts within 30 minutes
   (port scan, web attacks) — if so, this is part of a larger attack chain.

## Evidence
- Export the raw auth.log events linked to the alert (failed + any
  success attempts) via "Export raw events."
- Record in incident notes: src_ip, dst_ip (web-01 or srv-01), targeted
  username(s), attempt count, time window, and whether a success occurred.
- If a success occurred: capture a screenshot of the alert/incident
  timeline showing the escalation from HIGH to CRITICAL, and upload it as
  evidence with its hash.
- [FILL IN: if your IDS produces its own alert log separate from the
  platform's `alerts` table, note where that raw IDS output lives so it
  can be attached as supporting evidence.]

## Containment
- If attempts only (no success): consider "Block IP" once the threshold
  is confirmed and the attack is ongoing.
- If a success occurred: this is now a suspected account compromise.
  - Immediately "Disable account" for the compromised username.
  - "Block IP" for the source.
  - Treat as an incident requiring lead sign-off, not routine triage.
- Every containment action requires a human confirmation click — no
  automatic blocking is permitted, per project rules of engagement.
- [FILL IN: confirm the block mechanism — nftables set on fw-01 via an
  authenticated script, as in the original spec. This part is unaffected
  by the switch away from Suricata/Docker, but confirm it's still built
  this way in your `backend/`.]

## Recovery
- If an account was disabled, coordinate a password reset before
  re-enabling it (do not just re-enable with the same credentials).
- If an IP was blocked, confirm legitimate SSH access from other
  approved IPs still works.
- Review auth.log after containment to confirm no further failed/success
  attempts from the blocked source.

## Closure
- If benign (e.g. a teammate mistyping credentials repeatedly), close as
  FALSE POSITIVE with a reason.
- If a real attack with no success, close as RESOLVED once blocked,
  noting root cause ("password brute force, no compromise") and lessons
  learned (e.g. "recommend disabling password auth, use key-based SSH").
- If a success occurred, this must go through full incident closure:
  root cause, remediation taken (account reset), and lessons learned,
  signed off by a lead.
