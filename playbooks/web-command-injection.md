# Command Injection Playbook — `WEB-CMD-001`

**Category:** Web  
**Initial Severity:** HIGH  
**MITRE ATT&CK:** T1059 — Command and Scripting Interpreter  
**Source:** Nginx access and error logs

## 1. Triage — Analyst

1. Open the alert and identify the source IP, target host, endpoint, parameter, timestamp, HTTP method and status code.
2. Identify the shell separator and command that triggered the rule (`; id`, `| whoami`, `&& cat`, `|| sh` and similar) and inspect the linked event.
3. Check the response for command output such as `uid=0` or a username; that proves execution, not just an attempt.
4. Review related events from the same source and target over the previous 30 minutes, including `WEB-SCAN-001`, `NET-PORTSCAN-001` and `WEB-BF-001` where relevant.
5. Treat this as a host-level event on `soc-01`; the web process has no container boundary behind it.

## 2. Evidence Collection — Analyst

1. Preserve the original event, request details, timestamp and alert ID.
2. Export the linked Nginx access and error logs.
3. Capture the response body if it contains command output, and attach it to the incident.
4. Record the matched command, endpoint, parameter, source IP and whether output was observed.
5. Link all evidence to the alert or incident.

## 3. Investigation — Analyst

1. Determine whether the request was a probe, a credible exploitation attempt or confirmed command execution.
2. Search the host for the command's side effects: new files, users, cron entries, listening ports and reverse shells.
3. Identify the affected host, the privileges the web process runs with and the data it can reach.
4. Document findings and separate confirmed facts from assumptions.
5. Escalate any suspected command execution to the SOC Lead immediately.

## 4. Containment — Lead / Admin

1. Review the analyst's findings and approve containment; confirmed or plausible execution requires immediate action.
2. For a probe with no sign of execution, continue monitoring.
3. For a credible exploitation attempt, record `block IP` for the source and confirm it after approval.
4. For suspected execution, record `block IP` and `isolate host`; treat `soc-01` as compromised until proven otherwise and involve the lead.
5. Record every containment action, its reason, owner and timestamp.

## 5. Remediation and Recovery — Admin / Application Owner

1. Fix the endpoint to avoid shell invocation: use language-native APIs, allow-listed values or escaped arguments.
2. Inspect the web root for web shells or modified files and remove them.
3. Review accounts, `authorized_keys` and scheduled jobs for persistence.
4. Rebuild the host from the clean baseline when execution is confirmed; do not clean in place.
5. Reset the vulnerable application (DVWA) to a known-clean state.
6. Test the fix in an authorized environment and confirm the command no longer executes.

## 6. Closure — Admin

1. Record the final findings, impact, root cause and remediation actions.
2. For authorized testing, record the authorization and use the supported benign/false-positive disposition.
3. For an unsuccessful attempt, document the evidence and the remediation that closes the vulnerability.
4. For confirmed execution, verify containment, rebuild and recovery before requesting closure.
5. Close the incident only when all closure criteria are met.

**Important:** Command injection that reached the shell is host-level compromise; a successful command on `soc-01` grants the same access as the web service account.

## Related

- **Rule definition:** `rules/command_injection.yaml`
- **Reproduce:** `attack-sim/sqli-xss.sh <target> cmdi`
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
