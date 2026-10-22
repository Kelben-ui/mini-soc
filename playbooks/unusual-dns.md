# Unusual DNS Activity Playbook — `DNS-ANOMALY-001`

**Category:** DNS  
**Initial Severity:** LOW  
**MITRE ATT&CK:** T1071.004 — Application Layer Protocol: DNS  
**Source:** Custom IDS DNS sniffer, signature `9000004`

## 1. Triage — Analyst

1. Open the alert and identify the host, direction of the queries, timestamp and query volume.
2. Confirm the trigger: a DNS label longer than 50 characters, or more than 100 queries per minute from one host. Inspect the linked events.
3. Identify the queried names. Long random labels are the shape of tunnelling; ordinary names at a high rate are usually noise.
4. Determine who is sending: the SOC host itself (outbound exfiltration, more serious) or an external source (probe, usually noise).
5. Review related events from the same source over the previous 30 minutes, including `NET-OUTBOUND-001`, `SSH-SUCCESS-001` and web alerts; tunnelling is a post-compromise behaviour.

## 2. Evidence Collection — Analyst

1. Preserve the original events, timestamps and alert ID.
2. Export the linked IDS DNS events.
3. Record the queried names, query rate, label length, originating host and resolver involved.
4. Record the direction of the traffic and any volume of data it could carry.
5. Link all evidence to the alert or incident.

## 3. Investigation — Analyst

1. Determine whether the host is the victim of probe traffic or the sender of tunnelling or exfiltration queries.
2. Identify the queried domain, its reputation and whether it is registered recently or resolves to infrastructure the organization does not use.
3. Check the process and user that generated the queries and what data it sent.
4. Document findings and separate confirmed facts from assumptions.
5. Escalate any case where the SOC host is the sender to the SOC Lead; treat it as suspected malware.

## 4. Containment — Lead / Admin

1. Review the analyst's findings and approve containment.
2. If the host is sending unusual DNS, record `isolate host` and investigate for malware or a tunnelling agent.
3. If the host is receiving probe-like DNS, record `block IP` for the source where warranted and confirm it after approval.
4. For known-good resolver traffic, change the allow-list or threshold instead of blocking.
5. Record every containment action, its reason, owner and timestamp.

## 5. Remediation and Recovery — Admin / Host Owner

1. Remove the tunnelling agent or reconfigure the application that generated the queries.
2. Block the suspicious domain at the resolver and confirm the queries stop.
3. Review the host for the compromise that preceded the tunnelling, including new accounts, keys and scheduled tasks.
4. Rebuild the host from the clean baseline when malware is confirmed.
5. Tune the IDS label-length and query-rate thresholds if the alert was caused by a legitimate service.
6. Confirm that normal service, logging and detection are functioning after recovery.

## 6. Closure — Admin

1. Record the final findings, the queried names, direction, impact and remediation actions.
2. For authorized test traffic, record the authorization and use the supported benign/false-positive disposition.
3. For tunnelling or exfiltration, verify containment, agent removal and host recovery before requesting closure.
4. For probe-like traffic with no compromise, document the source and the threshold change if one was made, then close the alert as resolved.
5. Close the incident only when all closure criteria are met.

**Important:** Unusual DNS is a low-severity signal on its own; treat it as high severity only when the local host is the sender.

## Related

- **Rule definition:** `rules/unusual_dns.yaml`
- **Reproduce:** `attack-sim/dns-tunnel-sim.sh` (run **on the instance**)
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
