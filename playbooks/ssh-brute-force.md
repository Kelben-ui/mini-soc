# Playbook: SSH Brute Force

## Triage
1. Confirm alert: repeated auth.log failures, same src_ip, short window.
2. Note src_ip, target host, attempt count, time range.

## Evidence
- Export raw auth.log lines for that IP as evidence.
- Screenshot the alert on the dashboard.

## Containment
- Block source IP on fw-01 (nftables) after analyst confirmation.
- Disable the targeted account if compromise suspected.

## Recovery
- Reset password on targeted account.
- Confirm no successful login occurred during the window.

## Closure
- Add root cause and lessons learned.
- Mark incident RESOLVED with summary.
