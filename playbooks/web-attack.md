# Playbook: Web Attack (SQL Injection / XSS / Command Injection / Traversal)

## Trigger
Covers several rules against Nginx/DVWA traffic, all detected from decoded
URI/body content:
- SQL injection (HIGH) — quotes with OR/UNION/SLEEP, SQL comment patterns
- Cross-site scripting (MEDIUM) — `<script`, event handlers, `javascript:`
- Command injection (HIGH) — `;`, `|`, `&&` followed by shell commands on
  the DVWA exec page
- Directory traversal / LFI (HIGH) — `../`, `/etc/passwd`, `php://`
- Scanner user agent (MEDIUM) — sqlmap, nikto, nmap, gobuster in
  User-Agent
- Web login brute force (HIGH) — ≥20 POSTs to the DVWA login, same
  src_ip, within 2 minutes

[FILL IN: confirm your custom IDS evaluates these from the collector's
normalized events (URL-decoded URI/body per the common event format), or
whether it inspects raw Nginx logs itself. This affects whether "decoded
payload" evidence is guaranteed available — see Evidence below.]

## Triage
1. Identify which rule(s) fired and the payload pattern matched.
2. Check the decoded URI/body in the event to confirm it's a real
   exploit attempt and not a false positive (e.g. a legitimate apostrophe
   in a form field wrongly matching a SQLi pattern).
3. Check the HTTP response status/outcome — did the payload appear to
   succeed (e.g. 200 with data returned) or fail (e.g. 403, 500, WAF
   block if any)?
4. Check if this src_ip triggers other alerts within 30 minutes (port
   scan, SSH brute force) — if so, treat as part of a larger attack chain.
5. For scanner user-agent alerts specifically: this is reconnaissance,
   not necessarily exploitation — check if it's followed by targeted
   SQLi/XSS/traversal attempts from the same IP.

## Evidence
- Export the raw Nginx access/error log events linked to the alert,
  including the decoded payload, via "Export raw events."
- Screenshot the alert detail showing the decoded URI/body as displayed
  on the dashboard.
- Record in incident notes: src_ip, targeted endpoint (e.g. DVWA SQLi
  page), payload used, HTTP status returned, and whether data exposure
  or command execution appears to have succeeded.
- [FILL IN: if the attack appears to have succeeded (e.g. SQLi returned
  data, command injection executed), note here what additional evidence
  to capture — e.g. a screenshot of the DVWA response itself, not just
  the log line.]

## Containment
- Single/isolated alert (e.g. one scanner user-agent hit): monitor,
  no action required yet.
- Confirmed exploitation attempt (SQLi/XSS/command injection/traversal
  with a plausible payload): "Block IP" and escalate to INCIDENT.
- If command injection or traversal appears to have succeeded (shell
  access or file read confirmed): treat web-01 as potentially compromised
  — "Isolate host" in addition to blocking the source IP, and involve a
  lead immediately.
- Every containment action requires a human confirmation click — no
  automatic blocking is permitted.
- [FILL IN: confirm block/isolate mechanisms are unaffected by the move
  away from Docker — i.e., are these actions still authenticated scripts
  run against fw-01/web-01 directly, or does removing Docker change how
  web-01 is isolated (e.g. no container to simply stop)?]

## Recovery
- If web-01 was isolated, confirm DVWA/Nginx integrity before
  reconnecting it (check for unexpected files, modified configs, new
  user accounts, or cron jobs).
- Reset the DVWA database to a known-clean state before resuming testing
  (this project's own reset script — see repo `sample-data/` or the
  reset script from Member 6 test tooling).
- If credentials or data exposure is suspected, note this for a wider
  password rotation, even in the lab context.

## Closure
- If benign (e.g. a teammate's own testing traffic from an approved IP),
  close as FALSE POSITIVE with a reason.
- If a real attack with no confirmed success, close as RESOLVED, noting
  root cause (e.g. "unpatched DVWA SQLi endpoint, exploited via `id`
  parameter") and lessons learned.
- If exploitation succeeded, this requires full incident closure: root
  cause, remediation (e.g. host isolated then rebuilt/reset, input
  validation gap identified), and lessons learned, signed off by a lead.
