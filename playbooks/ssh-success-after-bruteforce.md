# SSH Login Success After Brute-force Playbook — `SSH-SUCCESS-001`

**Category:** Authentication  
**Initial Severity:** CRITICAL  
**MITRE ATT&CK:** T1078 — Valid Accounts  
**Source:** `auth.log`

## 1. Triage — Analyst

1. Open the alert and identify the source IP, target host, username and the timestamp of the accepted login.
2. Confirm the preceding brute-force alert (`SSH-BF-001`) on the same source within the previous 30 minutes; this alert only fires after an open brute-force alert.
3. Assume the account is compromised and identify what the account can reach: home directory, sudo rights, running services and shared credentials.
4. Review related events from the same source over the previous 30 minutes, including `NET-PORTSCAN-001`, web alerts, `NET-OUTBOUND-001` and `DNS-ANOMALY-001`; a multi-stage intrusion is expected.
5. Escalate to the SOC Lead immediately; do not continue triage alone.

## 2. Evidence Collection — Analyst

1. Preserve the original events, timestamps and alert ID.
2. Export the `auth.log` events for both the failed burst and the accepted login, and keep them under the same incident.
3. Record the source IP, username, target host, timestamp of the `Accepted` line and any session or command evidence available.
4. Record every other alert the source raised in the same window, and every action the account performed after the login.
5. Link all evidence to the alert or incident.

## 3. Investigation — Analyst

1. Determine what the attacker did after logging in: commands run, files read or changed, keys added, accounts created.
2. Check for persistence: new `authorized_keys` entries, new users, cron entries, modified `sudoers` and new scheduled services.
3. Establish the blast radius: which credentials and data the account could reach, and whether the host contacted anything unusual afterwards.
4. Document findings and separate confirmed facts from assumptions.
5. Escalate the full timeline to the SOC Lead and treat the host as compromised until proven otherwise.

## 4. Containment — Lead / Admin

1. Record `block IP` for the source and confirm it immediately; keep the source blocked after the timeout expires.
2. Record `disable account` for the compromised user and reset its credentials and `authorized_keys` out-of-band.
3. Record `isolate host` for the affected host; it stays isolated until the investigation and rebuild are complete.
4. Involve the lead in every decision; this is a compromise, not an attempt.
5. Record every containment action, its reason, owner and timestamp.

## 5. Remediation and Recovery — Admin / Host Owner

1. Rotate every credential the compromised account could reach, including service accounts, API tokens and keys in the user's files.
2. Remove unauthorized users, keys, cron entries and `sudoers` changes.
3. Rebuild the host from the clean baseline when compromise is confirmed; do not clean in place.
4. Confirm no lingering sessions, tunnels or scheduled tasks survive the password reset and rebuild.
5. Enable key-only SSH (`PasswordAuthentication no`) so the same password guessing cannot succeed again.
6. Confirm that normal service, logging and detection are functioning after recovery.

## 6. Closure — Admin

1. Record the final findings, the attacker's actions, impact, root cause and recovery decisions.
2. Use the benign/false-positive disposition only with documented proof that the login was an authorized test with correct credentials.
3. For a real compromise, verify containment, credential rotation and rebuild before requesting closure.
4. Record the lessons learned, including any detection or hardening gap that allowed the login to succeed.
5. Close the incident only when all closure criteria are met.

**Important:** A successful SSH login after a brute-force burst is a suspected compromise, not an attempt; it must never be closed without documented proof of authorization.

## Related

- **Rule definition:** `rules/ssh_success_after_bruteforce.yaml`
- **Reproduce:** `attack-sim/ssh-brute-force.sh <target> testuser passlist.txt` (the passlist ends with the real password)
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
