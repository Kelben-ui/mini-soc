# Platform Security Test

## Scope
SQLi, XSS, broken access control/IDOR, JWT tampering, upload abuse, exposed ports scan of EC2 host, IPS helper injection.

## Test Plan (Phase 9.2)
- SQLi/XSS: validate input sanitization, parameterized queries, Jinja2 autoescape
- Broken access control/IDOR: test RBAC on protected endpoints
- JWT tampering: test invalid/expired tokens, role escalation attempts
- Upload abuse: file type/size limits, evidence storage constraints
- EC2 exposed ports scan: verify only required ports exposed (nginx 80/443, SSH 22 as needed)
- IPS helper injection: validate soc-block input validation, allow-list enforcement

## Status
Pending execution against EC2 per Phase 9.2. Target: No open High findings.

Automated coverage already in place (task 4.7):
- `backend/tests/test_actions_route.py` exercises the response-action
  endpoints: non-IPv4 targets, allow-listed targets, missing
  `confirm: true`, non-block action types, and a missing helper are all
  refused without ever touching the firewall; only a validated, confirmed,
  allow-list-clean IPv4 reaches the helper.
- `deploy/soc-block` re-validates the address and refuses
  allow-listed/garbage input even if called directly (defence in depth);
  `deploy/sudoers/mini-soc-soc-block` grants the backend user nothing but
  that one script.
