# Playbook: Port Scan / Reconnaissance

## Trigger
Rule: Port scan — ≥20 distinct destination ports from one source IP within
1 minute, detected from nftables drop/accept logs and/or [FILL IN: your
IDS's port-scan detection method — does it do its own packet-level
detection, or does it consume nftables logs like the original spec?].
Severity: MEDIUM.

[FILL IN: confirm your IDS emits an event/alert for this, and what field
names it uses — e.g. does it call this `port_scan`, `recon`, something
else? Match whatever your detection engine's rule ID and event schema use.]

## Triage
1. Confirm the alert: ≥20 distinct dest ports, same src_ip, within 1 minute.
2. Check the alert's `count` and `evidence` fields for the actual port list —
   [FILL IN: does your IDS log which ports were scanned, or only the count?
   If only count, note that as a limitation and rely on raw event export
   instead].
3. Check if this src_ip triggers further alerts within 30 minutes
   (correlation).
   - If NO further alerts → likely a benign/authorized scan (e.g. the
     approved test IP), proceed to Closure.
   - If YES → this is stage 1 of a multi-stage attack. Treat the whole
     correlated chain as one incident, not this alert alone.

## Evidence
- From Alert Detail, use "Export raw events" to save the scanned-port
  list as a log file (attached automatically as evidence on the incident).
- Record in incident notes: src_ip, dst_ip/host, first_seen, last_seen,
  distinct port count.
- [FILL IN: if your IDS has its own log format/output location — not
  eve.json since Suricata is out — note the exact path/table here so
  whoever runs this playbook knows where to pull raw evidence from
  directly if the export button fails.]

## Containment
- Monitor only if the scan stands alone with no follow-on activity.
- If it correlates within 30 minutes with SQLi, XSS, command injection, or
  SSH brute force from the same src_ip → escalate to INCIDENT and apply
  "Block IP" containment against the whole chain, not just this alert.
- [FILL IN: your block mechanism — the original spec blocked via an
  nftables set on fw-01 through an authenticated script. Confirm this
  is unchanged, since it doesn't depend on Suricata or Docker.]

## Recovery
- If the source IP was blocked, confirm normal traffic from other IPs is
  unaffected.
- No service restart is required — a scan alone does not disrupt any
  service.
- If later unblocked (e.g. reclassified as false positive), confirm the
  IP can reach allowed ports (22, 80) again.

## Closure
- If benign (e.g. the approved test IP), close as FALSE POSITIVE with a
  reason.
- If part of a correlated attack chain, close the alert as resolved once
  the parent incident is resolved — do not close it standalone.
- Otherwise, document findings (ports targeted, duration, any pattern)
  and close.
