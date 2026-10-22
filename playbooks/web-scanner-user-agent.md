# Scanner User-agent Playbook — `WEB-SCAN-001`

**Category:** Web  
**Initial Severity:** MEDIUM  
**MITRE ATT&CK:** T1595 — Active Scanning  
**Source:** Nginx access logs

## 1. Triage — Analyst

1. Open the alert and identify the source IP, target host, requested path, timestamp and status code.
2. Confirm the User-Agent string and which scanner token matched: `sqlmap`, `nikto`, `nmap` or `gobuster`.
3. Check the source against the allow-list (`rules/allowlist.yaml`). An approved scanner or analyst IP is not an attack.
4. Review related events from the same source over the previous 30 minutes. Reconnaissance with no follow-on is usually authorized scanning; reconnaissance followed by `WEB-SQLI-001`, `WEB-CMD-001`, `WEB-LFI-001`, `WEB-BF-001` or `NET-PORTSCAN-001` is stage 1 of an attack chain.
5. Note the endpoints the scanner enumerated; they are the ones the attacker will target next.

## 2. Evidence Collection — Analyst

1. Preserve the original event, User-Agent, requested path, timestamp and alert ID.
2. Export the linked Nginx request lines for the source IP.
3. Record the source IP, User-Agent, requested paths and first/last seen times.
4. Record whether the source appears on the allow-list and who authorized the scan.
5. Link all evidence to the alert or incident.

## 3. Investigation — Analyst

1. Determine whether the traffic was authorized scanning, unsanctioned reconnaissance or stage 1 of an attack chain.
2. List the endpoints and parameters the scanner probed and check them for follow-on exploitation.
3. Identify any data the scanner retrieved and any authentication attempts it made.
4. Document findings and separate confirmed facts from assumptions.
5. Escalate a correlated chain to the SOC Lead and promote it to a single incident.

## 4. Containment — Lead / Admin

1. Review the analyst's findings and approve proportionate containment actions.
2. For standalone reconnaissance with no follow-on, continue monitoring; do not block an authorized scanner.
3. For reconnaissance followed by exploitation attempts, record `block IP` for the chain source and confirm it after approval. Use 1800 s for pure reconnaissance and 3600 s when exploitation followed.
4. Block the entire chain as one incident, not each alert separately.
5. Record every containment action, its reason, owner and timestamp.

## 5. Remediation and Recovery — Admin / Application Owner

1. For reconnaissance alone, no service change is required; confirm that no endpoint was exposed beyond its intended scope.
2. For a chain, apply the remediation from the exploitation playbook that matched the follow-on alerts.
3. Confirm the scanner is removed from the allow-list if its authorization has expired.
4. Verify that normal service and logging are functioning after any containment.
5. Add any future approved scanner to the allow-list so its traffic stops alerting.

## 6. Closure — Admin

1. Record the final findings, the tools identified, the endpoints probed and the authorization status.
2. For authorized testing, record the authorization and use the supported benign/false-positive disposition.
3. For reconnaissance that formed part of a chain, close this alert inside the parent incident.
4. For unsanctioned reconnaissance, document the exposure it found and the tracking action taken, then close the alert as resolved.
5. Close the incident only when all closure criteria are met.

**Important:** A scanner User-Agent identifies the tool in use, not the intent of its operator; the authorization status determines whether this is a false positive.

## Related

- **Rule definition:** `rules/scanner_user_agent.yaml`
- **Reproduce:** `attack-sim/scanner-ua.sh <target>`
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
