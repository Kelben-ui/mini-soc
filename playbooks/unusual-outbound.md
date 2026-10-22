# Unusual Outbound Connection Playbook — `NET-OUTBOUND-001`

**Category:** Network  
**Initial Severity:** MEDIUM  
**MITRE ATT&CK:** T1041 — Exfiltration Over C2 Channel  
**Source:** Custom IDS signature `9000005`, from nftables `SOC_OUT:` log lines

## 1. Triage — Analyst

1. Open the alert and identify the source host, destination IP, destination port and timestamp.
2. Confirm the trigger: the host opened a connection to a destination port outside the allow-list (`53`, `80`, `443`, `123`). Inspect the linked events.
3. Identify the process that opened the connection (`ss -tnp`, `lsof -i`) and the user it runs as.
4. Review related events from the same source over the previous 30 minutes, including `DNS-ANOMALY-001`, `SSH-SUCCESS-001` and web alerts; outbound traffic is a classic post-compromise signal.
5. Check the destination against known-good services and against any ticket for an approved change.

## 2. Evidence Collection — Analyst

1. Preserve the original events, timestamps and alert ID.
2. Export the linked `SOC_OUT:` events.
3. Record the destination IP, destination port, owning process, user and connection duration.
4. Record the volume and pattern of the traffic, including whether it is periodic or sustained.
5. Link all evidence to the alert or incident.

## 3. Investigation — Analyst

1. Determine whether the connection is legitimate egress, a mis-configured service or command-and-control or exfiltration.
2. Identify the process owner, its expected behaviour and whether that destination is part of it.
3. Check the destination's reputation and whether it belongs to a known provider or to anonymous infrastructure.
4. Document findings and separate confirmed facts from assumptions.
5. Escalate unexplained outbound connections to the SOC Lead, especially where a prior compromise exists.

## 4. Containment — Lead / Admin

1. Review the analyst's findings and approve containment.
2. For a known-good service, update the egress allow-list instead of blocking; do not break legitimate egress.
3. For a suspicious or unexplained destination, record `block IP` for the destination and confirm it after approval.
4. For suspected command-and-control, record `isolate host` and involve the lead.
5. Record every containment action, its reason, owner and timestamp.

## 5. Remediation and Recovery — Admin / Host Owner

1. Stop the offending process or service and reconfigure it to use an approved destination and port.
2. Add the approved destination to the egress allow-list so the alert does not recur for legitimate traffic.
3. Confirm no further connections to the blocked destination after containment.
4. Review the host for the compromise that could have opened the connection, including new accounts, keys and scheduled tasks.
5. Rebuild the host from the clean baseline when malware is confirmed.
6. Confirm that normal service, logging and detection are functioning after recovery.

## 6. Closure — Admin

1. Record the final findings, the destination, owning process, impact and remediation actions.
2. For legitimate traffic, document the allow-list change and close the alert as resolved.
3. For an approved service that should have been allow-listed, close the alert as a false positive with the authorization recorded.
4. For command-and-control or exfiltration, verify containment, process removal and host recovery before requesting closure.
5. Close the incident only when all closure criteria are met.

**Important:** This rule fires on the destination port alone; identify the owning process before treating the connection as command-and-control.

## Related

- **Rule definition:** `rules/unusual_outbound.yaml`
- **Reproduce:** `attack-sim/outbound-conn.sh 203.0.113.5 4444` (run **on the instance**)
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
