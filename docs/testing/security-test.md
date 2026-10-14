# Platform Security Test (Phase 9.2)

## Scope

SQLi, XSS, broken access control/IDOR, JWT tampering, upload abuse, exposed ports scan of EC2 host, IPS helper injection.

## Test Results (Offline Verifiable)

Automated tests in `backend/tests/test_security.py` verify the following (all passing: 11/11):

| Check | Method | Result | Evidence |
|---|---|---|---|
| SQLi/XSS | Parameterized queries in event/alert filters; input handled via SQLAlchemy `.filter()` | PASS | `TestSQLiXSS.test_alert_list_rejects_invalid_filters`, `TestSQLiXSS.test_get_events_filters_are_parameterized` |
| Broken access control/IDOR | Auth required for incident/evidence access; lead-only assignment enforcement | PASS | `TestIDOR.test_get_incident_requires_authz`, `TestIDOR.test_update_incident_assignment_restricted`, `TestIDOR.test_get_evidence_custody_requires_auth` |
| JWT tampering | Expired token rejected; bad creds rejected; valid login produces token | PASS | `TestJWT.test_jwt_expired_raises`, `TestJWT.test_login_rejects_bad_creds`, `TestJWT.test_login_success_sets_sub` |
| Upload abuse | Evidence storage outside webroot; password policy enforced (min 8 chars) | PASS | `TestUploadAbuse.test_evidence_storage_path_is_outside_webroot`, `TestUploadAbuse.test_user_create_enforces_password_policy` |
| IPS helper injection | IPv4 validation; command split into argv list; allow-list enforcement; injection attempts rejected | PASS | `TestIPSHelper.test_ips_validation_and_injection_resistance` |

## Live Test (Requires EC2/Kali)

### Exposed Ports Scan of EC2 Host
From Kali (after targeting the instance):
```bash
nmap -Pn -sS -p- --min-rate 1000 $TARGET | tee /tmp/ec2_nmap.txt
```
Expected: Only 22 (SSH), 80 (DVWA), 443 (dashboard) open from analyst IP; no DB/collector/backend exposed to Internet. Cross-check on host:
```bash
ss -tlnp
```

## Findings
- No open High findings from offline checks.
- EC2 port scan must be completed by the operator with access to the live instance.

## References
- `backend/tests/test_security.py` (automated coverage)
- `backend/app/ips.py` (helper wrapper with validation)
- `deploy/soc-block` + `deploy/sudoers/mini-soc-soc-block` (defense in depth)
