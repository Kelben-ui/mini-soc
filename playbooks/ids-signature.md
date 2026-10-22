# Generic IDS Signature Playbook — `IDS-SIG-001`

**Category:** IDS  
**Initial Severity:** HIGH  
**MITRE ATT&CK:** T1059 — Command and Scripting Interpreter  
**Source:** Custom IDS (`ids/live_ids_ips.py`), signature taken from `ids/ids.yaml`

## 1. Triage — Analyst

1. Open the alert and identify the source IP, target host and timestamp.
2. Read the signature `id`, `msg`, `priority` and `category` on the linked event to identify which signature fired.
3. Map the signature to the real scenario: `9000001` port scan, `9000002` SSH brute force, `9000003` SYN flood, `9000004` DNS tunnelling, `9000005` unusual outbound connection.
4. Check whether an alert of the mapped type already exists for the same source and window; the IDS is a second view of the same activity and must not be counted as a second attack.
5. Review related events from the same source over the previous 30 minutes and open the mapped playbook for the scenario.

## 2. Evidence Collection — Analyst

1. Preserve the original event, signature fields, timestamps and alert ID.
2. Export the linked IDS events for the source.
3. Record the signature ID, message, priority, category, source IP and any destination details.
4. Record the matching rule alert for the same activity, where one exists, and keep both under one incident.
5. Link all evidence to the alert or incident.

## 3. Investigation — Analyst

1. Determine which scenario the signature really describes and apply that scenario's triage steps.
2. Verify whether the same activity already produced a dedicated rule alert; if so, investigate the pair together and do not duplicate the finding.
3. Identify the affected host or service and the activity the signature describes.
4. Document findings and separate confirmed facts from assumptions.
5. Escalate per the mapped scenario: SSH success and suspected execution go to the SOC Lead immediately.

## 4. Containment — Lead / Admin

1. Apply the containment decision of the mapped scenario's playbook.
2. Record `block IP` for the source where the mapped scenario calls for it, and confirm it after approval.
3. Record `disable account` or `isolate host` where the mapped scenario calls for them; those remain manual actions after they are recorded.
4. Do not block twice when a dedicated alert already triggered containment for the same source.
5. Record every containment action, its reason, owner and timestamp.

## 5. Remediation and Recovery — Admin / Host Owner

1. Apply the remediation of the mapped scenario's playbook.
2. For signature `9000002`, complete the SSH hardening from the SSH brute-force playbook: reset targeted credentials and switch to key-only authentication.
3. For signature `9000003`, apply the denial-of-service mitigations from the HTTP flood playbook.
4. For signature `9000004` or `9000005`, follow the unusual DNS or unusual outbound playbook.
5. Confirm that normal service, logging and detection are functioning after recovery.

## 6. Closure — Admin

1. Record the final findings, the signature that fired and the scenario it represents.
2. For authorized test traffic, record the authorization and use the supported benign/false-positive disposition.
3. When this alert duplicates a dedicated alert, close it inside that alert's incident rather than standalone.
4. For a unique signature with no dedicated alert, document the root cause and any tuning needed on the IDS, then close the alert as resolved.
5. Close the incident only when all closure criteria are met.

**Important:** `IDS-SIG-001` is a catch-all; the signature determines the real scenario, and duplicate telemetry for the same activity must never be counted as a second attack.

## Related

- **Rule definition:** `rules/ids_signature.yaml`
- **Reproduce:** `attack-sim/port-scan.sh <target>` (feeds the IDS)
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
