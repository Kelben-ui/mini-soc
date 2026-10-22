# Directory Traversal / LFI Playbook — `WEB-LFI-001`

**Category:** Web  
**Initial Severity:** HIGH  
**MITRE ATT&CK:** T1083 — File and Directory Discovery  
**Source:** Nginx access and error logs

## 1. Triage — Analyst

1. Open the alert and identify the source IP, target host, endpoint, parameter, timestamp, HTTP method and status code.
2. Identify the traversal token that triggered the rule (`../`, `/etc/passwd`, `php://`) and inspect the linked event.
3. Check the response for file contents such as a `root:x:0:0:` passwd line; that proves disclosure, not just a probe.
4. Review related events from the same source and target over the previous 30 minutes, including `WEB-SCAN-001`, `NET-PORTSCAN-001` and `WEB-CMD-001` where relevant.
5. Note which file the request targeted and whether the application runs as a privileged user.

## 2. Evidence Collection — Analyst

1. Preserve the original event, request details, timestamp and alert ID.
2. Export the linked Nginx access and error logs.
3. Capture the response body if file contents appear in it, and attach it to the incident. Treat any disclosed content as sensitive.
4. Record the matched token, endpoint, parameter, requested path, source IP and whether data was returned.
5. Link all evidence to the alert or incident.

## 3. Investigation — Analyst

1. Determine whether the request was a probe, a credible attempt or confirmed file disclosure.
2. Identify the files the application could read through the vulnerable endpoint and which of them were requested.
3. Check whether disclosed files contained credentials, keys or configuration that the attacker now holds.
4. Document findings and separate confirmed facts from assumptions.
5. Escalate confirmed disclosure of sensitive files, and any suspected host compromise, to the SOC Lead.

## 4. Containment — Lead / Admin

1. Review the analyst's findings and approve proportionate containment actions.
2. For an isolated probe with no disclosure, continue monitoring.
3. For confirmed disclosure or an active attack chain, record `block IP` for the source and confirm it after approval.
4. If sensitive files such as keys or credentials were read, record `isolate host` and involve the lead; rotate every secret they could expose.
5. Record every containment action, its reason, owner and timestamp.

## 5. Remediation and Recovery — Admin / Application Owner

1. Fix the endpoint to canonicalize paths and accept only allow-listed file names or directories.
2. Disable unnecessary PHP wrappers such as `php://` and run the web process as an unprivileged user.
3. Review the web root and configuration for unexpected files or modifications.
4. Reset the vulnerable application (DVWA) to a known-clean state.
5. Rotate every credential or key the disclosed files could have contained.
6. Test the fix in an authorized environment and confirm the traversal no longer returns file contents.

## 6. Closure — Admin

1. Record the final findings, impact, root cause and remediation actions.
2. For authorized testing, record the authorization and use the supported benign/false-positive disposition.
3. For an unsuccessful attempt, document the evidence and the remediation that closes the vulnerability.
4. For confirmed disclosure, verify containment, secret rotation and recovery before requesting closure.
5. Close the incident only when all closure criteria are met.

**Important:** A `../` or `php://` token in a request does not by itself prove that a file was read; confirm the response contents before reporting disclosure.

## Related

- **Rule definition:** `rules/traversal_lfi.yaml`
- **Reproduce:** `attack-sim/sqli-xss.sh <target> traversal`
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
