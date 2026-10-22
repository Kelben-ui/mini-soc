# Web Login Brute-force Playbook — `WEB-BF-001`

**Category:** Web  
**Initial Severity:** HIGH  
**MITRE ATT&CK:** T1110 — Brute Force  
**Source:** Nginx access logs

## 1. Triage — Analyst

1. Open the alert and identify the source IP, target host, timestamp and status codes.
2. Confirm the burst: at least 20 `POST` requests to `/dvwa/login.php` or `/dvwa/vulnerabilities/brute` from one source within 120 s. Inspect the linked events.
3. Look for a successful login from the same source after the burst: a redirect or `200` where earlier attempts returned `401` or `302` to the login page.
4. Identify the targeted account(s). One account means a targeted attack; several means password spraying.
5. Review related events from the same source over the previous 30 minutes, including `WEB-SCAN-001` and `NET-PORTSCAN-001` where relevant.

## 2. Evidence Collection — Analyst

1. Preserve the original events, request details, timestamps and alert ID.
2. Export the linked Nginx login `POST` events for the source IP.
3. Record the source IP, target path, attempt count, time window and targeted account(s).
4. Record whether any login succeeded, and the first request that returned a successful status.
5. Link all evidence to the alert or incident.

## 3. Investigation — Analyst

1. Determine whether the traffic was an unauthorized attempt, an authorized test or a successful credential compromise.
2. Identify how the account was guessed: brute force against one name or spraying many names with common passwords.
3. Check what the account did after any successful login: pages reached, content changed, sessions opened.
4. Document findings and separate confirmed facts from assumptions.
5. Escalate any successful credential use to the SOC Lead immediately; it changes the disposition to compromise.

## 4. Containment — Lead / Admin

1. Review the analyst's findings and approve containment; an ongoing attempt requires immediate action.
2. Record `block IP` for the source with a 3600 s timeout and confirm it after approval.
3. For a successful login, treat the account as compromised: record `disable account` for the web account and reset it out-of-band.
4. For a successful login, promote the alert to an incident and investigate the session as a full compromise.
5. Record every containment action, its reason, owner and timestamp.

## 5. Remediation and Recovery — Admin / Application Owner

1. Reset the targeted account's password to a strong, unique value and revoke its sessions.
2. Review the account's activity for content or configuration changes and undo any unauthorized ones.
3. Add rate-limiting or account lockout on the login endpoint.
4. Reset the vulnerable application (DVWA) to a known-clean state before resuming testing.
5. Test that legitimate logins from approved sources still work.
6. Confirm that normal service, logging and detection are functioning.

## 6. Closure — Admin

1. Record the final findings, attempt volume, targeted accounts, impact and remediation actions.
2. For authorized testing from an approved source, record the authorization and use the supported benign/false-positive disposition.
3. For an unsuccessful attempt, document the evidence and the hardening that was applied, then close the alert as resolved.
4. For a successful login, verify account disablement, credential reset and investigation of the session before requesting closure.
5. Close the incident only when all closure criteria are met.

**Important:** A burst of failed logins is an attempt; a successful login from the same source afterwards is a suspected compromise and must not be closed as routine noise.

## Related

- **Rule definition:** `rules/web_login_bruteforce.yaml`
- **Reproduce:** `attack-sim/sqli-xss.sh <target> bruteforce`
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
