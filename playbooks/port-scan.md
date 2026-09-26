# Playbook: Port Scan / Reconnaissance

## Triage
1. Confirm alert: >=20 distinct dest ports, same src_ip, 1 min.
2. Check if this IP triggers further alerts afterward (correlation).

## Evidence
- Export event list of scanned ports.

## Containment
- Usually monitor only; block if followed by exploit attempts.

## Closure
- If benign (approved test IP), close as FALSE POSITIVE with reason.
- Otherwise document and close.
