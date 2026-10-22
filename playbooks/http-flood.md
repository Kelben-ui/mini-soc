# HTTP Flood Playbook — `WEB-FLOOD-001`

**Category:** Web  
**Initial Severity:** MEDIUM  
**MITRE ATT&CK:** T1498 — Network Denial of Service  
**Source:** Nginx access logs

## 1. Triage — Analyst

1. Open the alert and identify the source IP, target host, timestamp and rate.
2. Confirm the trigger: at least 301 requests returning HTTP `301` from one source within 60 s. Inspect the linked events.
3. Check whether the host is saturated: review CPU, memory and connection counts (`top`, `ss -s`).
4. Distinguish one misbehaving client from a distributed flood by counting the distinct source IPs in the alert window.
5. Review related events from the same source over the previous 30 minutes, including `NET-PORTSCAN-001` and `WEB-SCAN-001`; a flood often follows discovery of a redirect endpoint.

## 2. Evidence Collection — Analyst

1. Preserve the original events, timestamps and alert ID.
2. Export the linked Nginx flood events.
3. Record the source IP or IPs, requests per second, duration, target endpoint and status codes.
4. Record the host's resource state during the flood and when it recovered.
5. Link all evidence to the alert or incident.

## 3. Investigation — Analyst

1. Determine whether the traffic was an authorized load test, a misbehaving client or a deliberate denial-of-service attempt.
2. Establish the impact: service degradation, failed legitimate requests or full outage.
3. Identify the endpoint being flooded and whether it is a discovered redirect or a legitimate service path.
4. Determine whether the sources are single or distributed; distributed traffic means the target is the whole service, not one client.
5. Escalate confirmed denial of service, and any distributed flood, to the SOC Lead.

## 4. Containment — Lead / Admin

1. Review the analyst's findings and approve containment; an active flood requires immediate action.
2. For a single source, record `block IP` with a 1800–3600 s timeout and confirm it after approval.
3. For distributed sources, note that blocking individual addresses is ineffective; raise the Security Group or an upstream mitigation with the provider instead.
4. Record every containment action, its reason, owner and timestamp.

## 5. Remediation and Recovery — Admin / Application Owner

1. Confirm the host recovers once the traffic stops; monitor CPU, connections and error rates.
2. Enable or tighten rate-limiting on the flooded endpoint and enable caching for redirect responses where appropriate.
3. Adjust the Security Group or an upstream deny rule if the flood came from many addresses.
4. Confirm that normal service, logging and detection are functioning.
5. Document the rate, duration and mitigation for the post-incident review.

## 6. Closure — Admin

1. Record the final findings, request rate, duration, impact and mitigation applied.
2. For an authorized load test, record the authorization and use the supported benign/false-positive disposition.
3. For a single-source flood, document the containment action and the timeout that lifted it, then close the alert as resolved.
4. For a distributed flood, verify the upstream mitigation is in place before requesting closure.
5. Close the incident only when all closure criteria are met.

**Important:** This rule matches requests returning HTTP `301` at high volume from one source; confirm the host impact before deciding between monitoring, blocking or an upstream mitigation.

## Related

- **Rule definition:** `rules/http_flood.yaml`
- **Reproduce:** replay only — `detection/tests/replay_test.py` and the synthetic log in `sample-data/`
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
