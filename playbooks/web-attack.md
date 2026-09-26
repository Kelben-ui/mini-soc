# Playbook: Web Attack (SQLi / XSS)

## Triage
1. Confirm alert: decoded URI/body matches SQLi or XSS pattern.
2. Identify src_ip, target endpoint, payload.

## Evidence
- Export the decoded payload and raw Nginx log line.
- Screenshot the DVWA request if reproducible.

## Containment
- Block source IP if attack is ongoing.

## Recovery
- Check DVWA/app logs for data exposure or modification.

## Closure
- Document payload, root cause, lessons learned.
