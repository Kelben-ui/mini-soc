# Port Scan Playbook — `NET-PORTSCAN-001`

**Category:** Network  
**Initial Severity:** MEDIUM  
**MITRE ATT&CK:** T1046 — Network Service Discovery  
**Source:** Custom IDS signature `9000001`, from nftables `SOC_DROP:` log lines

## 1. Triage — Analyst

1. Open the alert and identify the source IP, target host and scan window.
2. Confirm the trigger: at least 20 distinct destination ports from one source within 60 s. Inspect the linked events.
3. Check the source against the allow-list (`rules/allowlist.yaml`). An approved scanner or analyst IP is not an attack.
4. Review related events from the same source over the previous 30 minutes. Reconnaissance with no follow-on is usually authorized scanning; reconnaissance followed by `WEB-SQLI-001`, `WEB-CMD-001`, `WEB-LFI-001` or `SSH-BF-001` is stage 1 of an attack chain.
5. Note which ports responded as open; those are the services the attacker will target next.

## 2. Evidence Collection — Analyst

1. Preserve the original events, timestamps and alert ID.
2. Export the linked scanned-port events for the source IP.
3. Record the source IP, target host, first and last seen times and the distinct port count.
4. Record which ports were probed and which were open.
5. Link all evidence to the alert or incident.

## 3. Investigation — Analyst

1. Determine whether the traffic was authorized scanning, unsanctioned reconnaissance or stage 1 of an attack chain.
2. Identify the services on the open ports and whether any of them are exposed beyond their intended scope.
3. Check whether the source attempted authentication or exploitation after the scan.
4. Document findings and separate confirmed facts from assumptions.
5. Escalate a correlated chain to the SOC Lead and promote it to a single incident.

## 4. Containment — Lead / Admin

1. Review the analyst's findings and approve proportionate containment actions.
2. For standalone reconnaissance with no follow-on, continue monitoring; do not block an authorized scanner.
3. For reconnaissance followed by exploitation attempts, record `block IP` for the chain source and confirm it after approval. Use 1800 s for pure reconnaissance and 3600 s when exploitation followed.
4. Block the entire chain as one incident, not each alert separately.
5. Record every containment action, its reason, owner and timestamp.

## 5. Remediation and Recovery — Admin / Host Owner

1. For reconnaissance alone, no host change is required; confirm that only the intended services listen externally.
2. For a chain, apply the remediation from the exploitation playbook that matched the follow-on alerts.
3. Restrict the Security Group or firewall to the approved source addresses for any service that does not need public exposure.
4. Remove any service that was found open by mistake and confirm the change on the next scan.
5. Confirm that normal service, logging and detection are functioning.

## 6. Closure — Admin

1. Record the final findings, the ports probed, the services exposed and the authorization status.
2. For authorized testing, record the authorization and use the supported benign/false-positive disposition.
3. For reconnaissance that formed part of a chain, close this alert inside the parent incident.
4. For unsanctioned reconnaissance, document the exposure found and the tracking action taken, then close the alert as resolved.
5. Close the incident only when all closure criteria are met.

**Important:** A port scan is reconnaissance by default; the follow-on activity, not the scan itself, determines whether this is an incident.

## Related

- **Rule definition:** `rules/port_scan.yaml`
- **Reproduce:** `attack-sim/port-scan.sh <target>`
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
