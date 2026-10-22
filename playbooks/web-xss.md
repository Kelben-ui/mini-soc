# Cross-site scripting (XSS) Playbook — `WEB-XSS-001`

**Category:** Web  
**Initial Severity:** MEDIUM  
**MITRE ATT&CK:** T1059 — Command and Scripting Interpreter  
**Source:** Nginx access logs, with application logs where available

## 1. Triage — Analyst

1. Open the alert and identify the source IP, target host, endpoint, parameter, timestamp, HTTP method and status code.
2. Identify the XSS token that triggered the rule (`<script`, `javascript:`, `onerror=`, `onload=`) and inspect the linked event.
3. Read the decoded URI or body and confirm the token is an attack payload, not a legitimate string such as documentation text.
4. Check the response for the payload reflected or stored unencoded; that is what turns a probe into a real finding.
5. Review related events from the same source and target over the previous 30 minutes, including `WEB-SCAN-001`, `NET-PORTSCAN-001` and `WEB-CMD-001` where relevant.

## 2. Evidence Collection — Analyst

1. Preserve the original event, request details, timestamp and alert ID.
2. Export the linked Nginx access events with the decoded payload.
3. Capture the response body if the payload was reflected or stored, and attach it to the incident. Protect any personal data it contains.
4. Record the matched token, endpoint, parameter, source IP and whether the payload was reflected or stored.
5. Link all evidence to the alert or incident.

## 3. Investigation — Analyst

1. Determine whether the request was a probe, a credible attempt or a confirmed stored injection.
2. Review stored content such as guestbook entries, profiles and comments for the persisted payload.
3. Identify the affected endpoint, the pages other users would view and the accounts that could load the payload.
4. Document findings and separate confirmed facts from assumptions.
5. Escalate reflected or stored payloads, and any suspected account takeover, to the SOC Lead.

## 4. Containment — Lead / Admin

1. Review the analyst's findings and approve proportionate containment actions.
2. For an isolated probe with no reflection, continue monitoring.
3. For a reflected payload or an active attack chain, record `block IP` for the source and confirm it after approval.
4. For a stored payload, treat the impact as code execution in another user's browser: record `isolate host` and involve the lead.
5. Record every containment action, its reason, owner and timestamp.

## 5. Remediation and Recovery — Admin / Application Owner

1. Fix the endpoint to encode output for its context: HTML, attribute, JavaScript or URL.
2. Sanitize any accepted markup on input and add a Content Security Policy where the platform supports one.
3. Remove any stored payload from the affected pages and profiles.
4. Reset the vulnerable application (DVWA) to a known-clean state.
5. Revoke sessions or tokens if an account could have been taken over.
6. Test the fix in an authorized environment and confirm the payload no longer executes.

## 6. Closure — Admin

1. Record the final findings, impact, root cause and remediation actions.
2. For authorized testing, record the authorization and use the supported benign/false-positive disposition.
3. For a reflected attempt that was not stored, document the fix that removed the reflection and close the alert as resolved.
4. For stored payloads or account impact, verify containment and remediation before requesting closure.
5. Close the incident only when all closure criteria are met.

**Important:** A matched XSS token proves that a payload was sent; it does not prove that the payload was reflected, stored or executed. Confirm reflection or storage before reporting a confirmed finding.

## Related

- **Rule definition:** `rules/xss.yaml`
- **Reproduce:** `attack-sim/sqli-xss.sh <target> xss`
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
