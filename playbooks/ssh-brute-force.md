# SSH Brute-force Playbook — `SSH-BF-001`

**Category:** Authentication  
**Initial Severity:** HIGH  
**MITRE ATT&CK:** T1110 — Brute Force  
**Source:** `auth.log`

## 1. Triage — Analyst

1. Open the alert and identify the source IP, target host, timestamp and attempt count.
2. Confirm the burst: at least 10 failed `ssh_login` events from one source to one host within 300 s. Inspect the linked events.
3. Identify the targeted username(s). One account means a targeted attack; several means password spraying.
4. Check for a successful login from the same source. If `SSH-SUCCESS-001` also fired, treat this as a suspected compromise and escalate immediately.
5. Review related events from the same source over the previous 30 minutes, including `NET-PORTSCAN-001`, and check the source against the allow-list (`rules/allowlist.yaml`).

## 2. Evidence Collection — Analyst

1. Preserve the original events, timestamps and alert ID.
2. Export the linked `auth.log` failed-login events.
3. Record the source IP, target host, targeted username(s), attempt count, time window and whether a success occurred.
4. Record the matching IDS signature event (`9000002`) where present; it is the same activity seen by a second source, not a second attack.
5. Link all evidence to the alert or incident.

## 3. Investigation — Analyst

1. Determine whether the traffic was an authorized test, an unauthorized attempt or a successful credential compromise.
2. Identify whether the attack targeted one account or many, and whether any account was successfully guessed.
3. Check the host's exposure: whether password authentication is enabled and whether the targeted accounts are privileged.
4. Document findings and separate confirmed facts from assumptions.
5. Escalate any successful login, and any attack against a privileged account, to the SOC Lead.

## 4. Containment — Lead / Admin

1. Review the analyst's findings and approve containment; an ongoing attack requires immediate action.
2. Record `block IP` for the source with a 3600 s timeout and confirm it after approval.
3. For a successful login, follow the `SSH-SUCCESS-001` playbook: block the source, record `disable account` and treat the host as compromised.
4. Combine the `IDS-SIG-001` alert for signature `9000002` into this incident rather than handling it separately.
5. Record every containment action, its reason, owner and timestamp.

## 5. Remediation and Recovery — Admin / Host Owner

1. Reset the targeted account's password out-of-band and remove any unauthorized `authorized_keys`.
2. Confirm no new users, groups or scheduled jobs were created on the host.
3. Switch to key-only authentication (`PasswordAuthentication no`) and tighten `MaxStartups` so concurrent unauthenticated connections are limited.
4. Confirm that normal SSH from approved sources still works after the block.
5. Confirm that normal service, logging and detection are functioning.

## 6. Closure — Admin

1. Record the final findings, attempt volume, targeted accounts, impact and remediation actions.
2. For an authorized test from an approved source, record the authorization and use the supported benign/false-positive disposition.
3. For an unsuccessful attempt, document the evidence and the hardening that was applied, then close the alert as resolved.
4. For a successful login, verify containment, credential reset and host recovery before requesting closure.
5. Close the incident only when all closure criteria are met.

**Important:** This alert proves that guesses failed; a successful login from the same source is a separate CRITICAL alert (`SSH-SUCCESS-001`) and changes the disposition to compromise.

## Related

- **Rule definition:** `rules/ssh_brute_force.yaml`
- **Reproduce:** `attack-sim/ssh-brute-force.sh <target> testuser passlist.txt`
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
