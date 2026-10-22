# SQL Injection Playbook — `WEB-SQLI-001`

**Category:** Web  
**Initial Severity:** HIGH  
**MITRE ATT&CK:** T1190 — Exploit Public-Facing Application  
**Source:** Nginx access logs, with application/database logs where available

## 1. Triage — Analyst

1. Open the alert and identify the source IP, target host, endpoint, timestamp, HTTP method and status code.
2. Identify the SQLi pattern that triggered the rule and inspect the linked event.
3. Check whether the request came from an authorized test or scanner.
4. Review related events from the same source and target over the previous 30 minutes, including `WEB-SCAN-001`, `NET-PORTSCAN-001` and `WEB-BF-001` where relevant.
5. Do not treat an HTTP `200` response or database error as proof of successful exploitation.

## 2. Evidence Collection — Analyst

1. Preserve the original event, request details, timestamp and alert ID.
2. Collect relevant Nginx access/error logs and application/database logs, where available.
3. Capture response evidence if available and authorized. Protect sensitive data.
4. Record the matched pattern, affected endpoint, source IP and investigation findings.
5. Link all evidence to the alert or incident.

## 3. Investigation — Analyst

1. Determine whether the request was a suspicious probe, a credible exploitation attempt or a confirmed compromise.
2. Check available application and database evidence for unauthorized data access, database changes or unexpected query behavior.
3. Identify the affected application, database and potentially exposed data.
4. Document findings and distinguish confirmed facts from assumptions.
5. Escalate credible exploitation or suspected compromise to the SOC Lead.

## 4. Containment — Lead / Admin

1. Review the analyst's findings and approve proportionate containment actions.
2. For isolated suspicious requests without evidence of impact, continue monitoring.
3. For credible or repeated attacks, consider an authorized temporary WAF rule, rate limit or source restriction.
4. For confirmed compromise, coordinate restriction of the affected application or database access.
5. Isolate a host only when justified by the evidence and approved response procedure.
6. Record every containment action, its reason, owner and timestamp.

## 5. Remediation and Recovery — Admin / Application Owner

1. Fix the vulnerable query using parameterized queries or prepared statements.
2. Review database permissions and relevant logs for unauthorized access or changes.
3. Rotate compromised credentials and revoke exposed sessions or tokens where necessary.
4. Restore verified clean data or systems if required.
5. Test the fix in an authorized environment and confirm the vulnerability is no longer reproducible.
6. Confirm that normal service, logging and detection are functioning.

## 6. Closure — Admin

1. Record the final findings, impact, root cause and remediation actions.
2. For authorized testing, record the authorization and use the appropriate benign/false-positive disposition supported by the platform.
3. For an unsuccessful attempt, document the evidence and any outstanding vulnerability remediation.
4. For confirmed compromise, verify containment, remediation and recovery before requesting closure.
5. Close the incident only when all closure criteria are met.

**Important:** A matched SQLi pattern indicates suspicious activity; it does not by itself prove successful exploitation. Follow the platform's supported statuses and permissions for all alert and incident updates.

## Related

- **Rule definition:** `rules/sqli.yaml`
- **Reproduce:** `attack-sim/sqli-xss.sh <target> sqli`
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
