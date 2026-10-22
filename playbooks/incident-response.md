# SentinelX — Incident Response Playbook

> **Version:** 1.2 · **Deployment:** single Amazon EC2 instance (public
> host `mini-soc`, Ubuntu 24.04, hostname `soc-01`) · **Owner:** M6
>
> This is the **umbrella playbook**: the platform model, the universal steps that
> apply to every alert, the shared containment / closure / reporting rules, and
> the index of the per-alert playbooks in this directory.
>
> Each detection rule also has its own standalone playbook — the alert detail page
> loads the one for the rule that fired. `frontend/scripts/sync-playbooks.mjs`
> copies **every** playbook in this directory into the dashboard at build time, so
> there is still a single authored copy of each.

---

## 1. Platform model (read once)

The SentinelX runs as **one EC2 instance**. There is no separate firewall host:
the instance's own `nftables` ruleset *is* the firewall, and it both protects the
host and produces the network telemetry the SOC consumes.

```
attackers / analyst
        │
        ▼
  AWS Security Group  ──►  nftables (SOC_ACCEPT / SOC_DROP / SOC_OUT logging)
        │                          │
        ├─ :22  sshd ──────────────┤  auth.log
        ├─ :80  nginx → DVWA/PHP    │  nginx access/error log
        └─ :443 nginx → dashboard   │
                                   ▼
        soc-agent (tails logs) → collector (normalizes) → PostgreSQL events
                                   │
                                   ▼
                detection engine (evaluate rules → alerts → chains)
                                   │
                                   ▼
                     dashboard (triage, incidents, actions)
```

**Objects and how they relate**

| Object | Meaning | Where it lives in the UI |
|---|---|---|
| **Event** | One normalized log line from the collector. | Event explorer / linked from an alert. |
| **Alert** | A rule matched (possibly after a threshold). Has `status`. | Alerts list → Alert detail. |
| **Chain** | Two or more alerts from one source correlated within the window. | Chains page. |
| **Incident** | The container for an investigation: notes, evidence, response actions, timeline. | Incidents page. |

**Alert lifecycle** (enforced by `backend/app/routers/alerts.py`):

```
NEW ──► INVESTIGATING ──► CONTAINED ──► RESOLVED
  └──► FALSE POSITIVE        (also allowed from NEW / INVESTIGATING, reason required)
```

**Incident lifecycle** (enforced by `backend/app/routers/incidents.py`):

```
open ──► investigating ──► contained ──► resolved ──► closed   (only the admin can close)
```

## 2. Universal steps (every alert)

1. **Confirm** the alert is real: check the rule, the `count`, the time window and
   the linked raw **events** (Alert Detail → linked events). Reproduce the match
   mentally against the event payload.
2. **Correlate before reacting.** Open the **Chains** view for the source IP and
   look for related alerts in the last 30 minutes (port scan → web attack → SSH
   brute force is the expected multi-stage story). Treat a correlated set as
   **one incident**, not one alert at a time.
3. **Capture evidence.** Use **Export raw events** on the alert to attach the
   underlying log lines to the incident (stored with a SHA-256 hash and chain of
   custody). Add an **investigation note** with: source IP, target, first/last
   seen, count, and what you concluded.
4. **Decide containment.** Only `block IP` is *executable* by the platform
   (Section 3). Other response actions (`disable account`, `isolate host`,
   `reset credentials`) are recorded on the timeline and carried out
   out-of-band.
5. **Close out** with a root cause and lessons learned (Section 12).

> **Roles.** An analyst opens alerts, reads events and adds investigation notes.
> Evidence export, alert status changes, incident creation, response actions and
> incident status changes require a **lead or admin** role. **Only the admin
> closes an incident.**

> **Rules of engagement.** No action is automatic. `block IP` only takes effect
> after a human records it and then **confirms** it in the dashboard. The
> helper and the backend both refuse allow-listed addresses and anything that is
> not a bare IPv4 address.

## 3. Containment reference — "Block IP" (the only executable action)

**What it does.** `POST /api/actions/{id}/execute` runs
`/usr/local/sbin/soc-block add <ipv4> <timeout>` through `sudo` (see
`deploy/sudoers/mini-soc-soc-block`). The helper validates the address, refuses
allow-listed addresses, then adds it to the nftables `inet filter blocklist` set
with a timeout (default **3600 s**). The firewall immediately drops all traffic
from that address, and the timeout lifts the block automatically.

**How to use it**

1. On the **incident**, add a response action of type **`block IP`**, target =
   the bare attacker IPv4, with a short reason. This records the decision.
2. Click **Confirm / Execute** on that action. `status` moves `pending →
   executed` (or `failed`, with the helper's message shown).
3. To reverse early: **Unblock** on the action → `soc-block del <ipv4>`.

**Timeout choices**

| Scenario | Suggested timeout |
|---|---|
| Single-source web/recon noise, low confidence | 1800 s (30 min) |
| Confirmed exploitation / active SSH brute force | 3600 s (default) |
| Compromised-credential traffic (SSH success after BF) | keep blocked; extend/re-block manually after review |

**What it does *not* do.** It does not disable accounts or isolate hosts. Those
remain recorded actions + manual work (Section 12).

## 4. Rule → playbook index

Every rule has its own standalone playbook (loaded automatically when you open
an alert of that type). The "Scenario" column points at the shared section below
for the full context.

| Rule ID | Name | Severity | Trigger | Playbook | Scenario |
|---|---|---|---|---|---|
| WEB-SQLI-001 | SQL injection | HIGH | web request contains SQLi tokens | [`web-sqli.md`](web-sqli.md) | §7 |
| WEB-XSS-001 | Cross-site scripting | MEDIUM | web request contains XSS tokens | [`web-xss.md`](web-xss.md) | §7 |
| WEB-CMD-001 | Command injection | HIGH | web request contains `; id`, `\| whoami`, … | [`web-command-injection.md`](web-command-injection.md) | §7 |
| WEB-LFI-001 | Directory traversal / LFI | HIGH | web request contains `../`, `/etc/passwd`, `php://` | [`web-traversal-lfi.md`](web-traversal-lfi.md) | §7 |
| WEB-SCAN-001 | Scanner user agent | MEDIUM | UA contains sqlmap/nikto/nmap/gobuster | [`web-scanner-user-agent.md`](web-scanner-user-agent.md) | §6 |
| WEB-BF-001 | Web login brute force | HIGH | ≥20 `POST /dvwa/login.php` or `/dvwa/vulnerabilities/brute` from one `src_ip` / 120 s | [`web-login-bruteforce.md`](web-login-bruteforce.md) | §8 |
| WEB-FLOOD-001 | HTTP flood | MEDIUM | ≥301 requests with status 301 / 60 s from one `src_ip` | [`http-flood.md`](http-flood.md) | §9 |
| SSH-BF-001 | SSH brute force | HIGH | ≥10 failed `ssh_login` / 300 s (per src→dst) | [`ssh-brute-force.md`](ssh-brute-force.md) | §5 |
| SSH-SUCCESS-001 | Login success after brute force | CRITICAL | successful `ssh_login` (correlated to a BF alert) | [`ssh-success-after-bruteforce.md`](ssh-success-after-bruteforce.md) | §5 |
| NET-PORTSCAN-001 | Port scan | MEDIUM | nftables/IDS: ≥20 distinct ports from one source | [`port-scan.md`](port-scan.md) | §6 |
| IDS-SIG-001 | Generic IDS signature | HIGH | IDS alert that is not a mapped kind (SSH-sig, SYN flood) | [`ids-signature.md`](ids-signature.md) | §10 |
| DNS-ANOMALY-001 | Unusual DNS activity | LOW | IDS DNS-tunnelling signature (long labels / high rate) | [`unusual-dns.md`](unusual-dns.md) | §10 |
| NET-OUTBOUND-001 | Unusual outbound connection | MEDIUM | host connects out to a port outside 53/80/443/123 | [`unusual-outbound.md`](unusual-outbound.md) | §11 |

## 5. Scenario — SSH brute force / successful login

**Rules:** `SSH-BF-001` (HIGH) · `SSH-SUCCESS-001` (CRITICAL)  
**Source:** `auth.log`, with IDS signature `9000002` as a second view of the same activity

### Triage — Analyst

1. Confirm the failed-login burst: at least 10 failed `ssh_login` events from one source to one host within 300 s, and identify the targeted username(s). One account means a targeted attack; several means password spraying.
2. Check for a successful login from the same source. If `SSH-SUCCESS-001` fired, treat the account as compromised and escalate now.
3. For `SSH-SUCCESS-001`, confirm the open `SSH-BF-001` alert on the same source within the previous 30 minutes and identify what the account can reach.
4. Check the source against the allow-list (`rules/allowlist.yaml`).
5. Review related events over the previous 30 minutes, including `NET-PORTSCAN-001`; reconnaissance followed by brute force is the classic chain.

### Evidence Collection — Analyst

1. Preserve the original events, timestamps and alert IDs.
2. Export the `auth.log` events for the failed burst and, where one occurred, the accepted login.
3. Record the source IP, target host, targeted username(s), attempt count, time window and whether a success occurred.
4. Record the matching IDS signature event (`9000002`) where present; it is the same activity, not a second attack.
5. Keep the brute-force and success alerts under one incident.

### Investigation — Analyst

1. Determine whether the traffic was an authorized test, an unauthorized attempt or a successful compromise.
2. Identify whether the attack targeted one account or many, and whether any account was guessed.
3. For a successful login, identify the attacker's actions: commands run, files read or changed, keys added, users created and outbound connections opened.
4. Check the host's exposure: whether password authentication is enabled and whether the targeted accounts are privileged.
5. Escalate any successful login to the SOC Lead immediately.

### Containment — Lead / Admin

1. For an ongoing attack with attempts only, record `block IP` for the source with a 3600 s timeout and confirm it after approval.
2. For a successful login, record `block IP`, record `disable account` for the compromised user and reset its credentials and `authorized_keys` out-of-band, and record `isolate host` for the host.
3. Treat the host as compromised until proven otherwise; do not restore the account before the host is cleaned.
4. Record every containment action, its reason, owner and timestamp.

### Remediation and Recovery — Admin / Host Owner

1. Reset the targeted account's password out-of-band and remove unauthorized `authorized_keys` entries.
2. For a compromise, rotate every credential the account could reach and rebuild the host from the clean baseline.
3. Switch to key-only SSH (`PasswordAuthentication no`) and tighten `MaxStartups`.
4. Confirm no new users, keys or cron entries remain and that approved SSH still works.
5. Confirm that normal service, logging and detection are functioning.

### Closure — Admin

1. Record the final findings, attempt volume, targeted accounts, impact and remediation actions.
2. For an authorized test from an approved source, record the authorization and use the supported benign/false-positive disposition.
3. For an unsuccessful attempt, document the evidence and the hardening applied, then close the alert as resolved.
4. For a successful login, verify containment, credential rotation and host recovery before requesting closure.
5. Close the incident only when all closure criteria are met.

*Reproduce this scenario with `attack-sim/ssh-brute-force.sh` (see
`attack-sim/README.md`).*

## 6. Scenario — Network reconnaissance

**Rules:** `NET-PORTSCAN-001` (MEDIUM) · `WEB-SCAN-001` (MEDIUM)  
**Source:** nftables `SOC_DROP:`/`SOC_ACCEPT:` lines and IDS signature `9000001`; Nginx access logs for the scanner user-agent

### Triage — Analyst

1. For the port scan, confirm at least 20 distinct destination ports from one source within 60 s and note which ports responded as open.
2. For the scanner user-agent, confirm the `User-Agent` matched `sqlmap`, `nikto`, `nmap` or `gobuster` and note the requested paths.
3. Check the source against the allow-list (`rules/allowlist.yaml`).
4. Review related events from the same source over the previous 30 minutes. Reconnaissance with no follow-on is usually authorized scanning; reconnaissance followed by `WEB-SQLI-001`, `WEB-CMD-001`, `WEB-LFI-001`, `WEB-BF-001` or `SSH-BF-001` is stage 1 of an attack chain.
5. Note the services and endpoints the reconnaissance identified; they are the attacker's next targets.

### Evidence Collection — Analyst

1. Preserve the original events, timestamps and alert IDs.
2. Export the scanned-port events and the scanner request lines.
3. Record the source IP, target, first and last seen times, distinct port count or `User-Agent` string, and the paths probed.
4. Record whether the source appears on the allow-list and who authorized the scan.
5. Keep both alerts under one incident when they describe the same activity.

### Investigation — Analyst

1. Determine whether the traffic was authorized scanning, unsanctioned reconnaissance or stage 1 of an attack chain.
2. Identify the services and endpoints exposed and check them for follow-on exploitation.
3. Check whether the source attempted authentication or retrieved data after scanning.
4. Document findings and separate confirmed facts from assumptions.
5. Escalate a correlated chain to the SOC Lead and promote it to a single incident.

### Containment — Lead / Admin

1. For standalone reconnaissance with no follow-on, continue monitoring; do not block an authorized scanner.
2. For reconnaissance followed by exploitation attempts, record `block IP` for the chain source and confirm it after approval. Use 1800 s for pure reconnaissance and 3600 s when exploitation followed.
3. Block the entire chain as one incident, not each alert separately.
4. Record every containment action, its reason, owner and timestamp.

### Remediation and Recovery — Admin / Host Owner

1. For reconnaissance alone, confirm that only intended services and endpoints are exposed and restrict anything found open by mistake.
2. For a chain, apply the remediation from the exploitation playbook that matched the follow-on alerts.
3. Add future approved scanners to the allow-list and retire expired authorizations.
4. Confirm that normal service, logging and detection are functioning.

### Closure — Admin

1. Record the final findings, the ports probed or `User-Agent` seen, the endpoints enumerated and the authorization status.
2. For authorized testing, record the authorization and use the supported benign/false-positive disposition.
3. For reconnaissance that formed part of a chain, close these alerts inside the parent incident.
4. For unsanctioned reconnaissance, document the exposure found and the tracking action taken, then close the alert as resolved.
5. Close the incident only when all closure criteria are met.

## 7. Scenario — Web application attack (SQLi / XSS / command injection / LFI)

**Rules:** `WEB-SQLI-001` (HIGH) · `WEB-XSS-001` (MEDIUM) · `WEB-CMD-001` (HIGH) · `WEB-LFI-001` (HIGH)  
**Source:** Nginx access and error logs, with application/database logs where available

### Triage — Analyst

1. Open the alert and identify the source IP, target host, endpoint, parameter, timestamp, HTTP method and status code.
2. Identify the token that triggered the rule and inspect the linked event: SQLi tokens (`' or `, `union select`, `sleep(`), XSS tokens (`<script`, `javascript:`, `onerror=`), a shell separator followed by a command (`; id`, `| whoami`, `&& cat`) or traversal tokens (`../`, `/etc/passwd`, `php://`).
3. Read the decoded URI or body and confirm the token is an attack payload, not a legitimate string such as documentation text or an apostrophe in a form field.
4. Check the response for evidence of success: database output, a reflected or stored payload, command output such as `uid=0`, or file contents such as a `root:x:0:0:` line.
5. Review related events from the same source over the previous 30 minutes, including `WEB-SCAN-001`, `NET-PORTSCAN-001` and `WEB-BF-001`.

### Evidence Collection — Analyst

1. Preserve the original events, request details, timestamps and alert IDs.
2. Export the linked Nginx access and error logs.
3. Capture the response body where it shows database output, reflected content, command output or file contents, and attach it to the incident. Protect any personal or sensitive data it contains.
4. Record the matched token, endpoint, parameter, source IP, status code and whether data or execution was observed.
5. Link all evidence to the alert or incident.

### Investigation — Analyst

1. Determine whether the request was a probe, a credible exploitation attempt or a confirmed compromise.
2. Check the application and database for unauthorized data access, database changes or unexpected query behavior.
3. For command injection and LFI, treat the host as at risk: search for side effects such as new files, users, cron entries, listening ports and reverse shells.
4. Identify the affected application, database, host and potentially exposed data; command injection or LFI with success is a host-level event on `soc-01`.
5. Escalate confirmed exploitation, and any suspected compromise, to the SOC Lead.

### Containment — Lead / Admin

1. For an isolated probe with no evidence of impact, continue monitoring.
2. For a credible exploitation attempt, record `block IP` for the source and confirm it after approval.
3. For confirmed compromise, or for command injection or LFI with evidence of success, record `block IP` and `isolate host`; there is no container to stop, so this is a host-level review of `soc-01`.
4. Isolate a host only when justified by the evidence and the approved response procedure.
5. Record every containment action, its reason, owner and timestamp.

### Remediation and Recovery — Admin / Application Owner

1. Fix the vulnerable code: parameterized queries for SQLi, context-aware output encoding for XSS, no shell invocation for command injection, canonicalized allow-listed paths for LFI.
2. Review the web root and configuration for unexpected files or modifications and remove any web shells.
3. Remove stored payloads from affected pages, review database permissions and rotate any exposed credentials, sessions or tokens.
4. Reset the vulnerable application (DVWA) to a known-clean state; rebuild the host from the clean baseline when execution is confirmed.
5. Test the fix in an authorized environment and confirm the vulnerability is no longer reproducible.
6. Confirm that normal service, logging and detection are functioning.

### Closure — Admin

1. Record the final findings, impact, root cause and remediation actions.
2. For authorized testing, record the authorization and use the supported benign/false-positive disposition.
3. For an unsuccessful attempt, document the evidence and the remediation that closes the vulnerability, then close the alert as resolved.
4. For confirmed compromise, verify containment, remediation and recovery before requesting closure.
5. Close the incident only when all closure criteria are met.

## 8. Scenario — Web login brute force

**Rule:** `WEB-BF-001` (HIGH)  
**Source:** Nginx access logs

### Triage — Analyst

1. Confirm the burst: at least 20 `POST` requests to `/dvwa/login.php` or `/dvwa/vulnerabilities/brute` from one source within 120 s.
2. Look for a successful login from the same source after the burst: a redirect or `200` where earlier attempts returned `401`.
3. Identify the targeted account(s); one account means a targeted attack, several means password spraying.
4. Review related events over the previous 30 minutes, including `WEB-SCAN-001` and `NET-PORTSCAN-001`.

### Evidence Collection — Analyst

1. Preserve the original events, timestamps and alert ID.
2. Export the linked login `POST` events.
3. Record the source IP, target path, attempt count, targeted account(s) and the first request that returned a successful status.
4. Link all evidence to the alert or incident.

### Investigation — Analyst

1. Determine whether the traffic was an unauthorized attempt, an authorized test or a successful credential compromise.
2. Check what the account did after any successful login: pages reached, content changed, sessions opened.
3. Escalate any successful credential use to the SOC Lead immediately.

### Containment — Lead / Admin

1. For an ongoing attempt, record `block IP` with a 3600 s timeout and confirm it after approval.
2. For a successful login, treat the account as compromised: record `disable account`, reset the account out-of-band and promote the alert to an incident.
3. Record every containment action, its reason, owner and timestamp.

### Remediation and Recovery — Admin / Application Owner

1. Reset the targeted account's password and revoke its sessions.
2. Add rate-limiting or account lockout on the login endpoint and reset DVWA to a known-clean state.
3. Confirm that legitimate logins from approved sources still work and that logging is functioning.

### Closure — Admin

1. Record the final findings, attempt volume, targeted accounts, impact and remediation actions.
2. For authorized testing, record the authorization and use the supported benign/false-positive disposition.
3. For an unsuccessful attempt, document the hardening applied, then close the alert as resolved.
4. For a successful login, verify account disablement, credential reset and session investigation before requesting closure.
5. Close the incident only when all closure criteria are met.

## 9. Scenario — HTTP flood

**Rule:** `WEB-FLOOD-001` (MEDIUM)  
**Source:** Nginx access logs

> There is deliberately **no** attack-sim script for this: a burst of this volume
> from a laptop at an internet-facing instance resembles the DoS traffic AWS
> restricts. It is covered by `detection/tests/replay_test.py` and the synthetic
> nginx log in `sample-data/`.

### Triage — Analyst

1. Confirm the trigger: at least 301 requests returning HTTP `301` from one source within 60 s.
2. Check whether the host is saturated: CPU, memory and connection counts (`top`, `ss -s`).
3. Count the distinct source IPs in the window to distinguish one misbehaving client from a distributed flood.
4. Review related events over the previous 30 minutes; a flood often follows discovery of a redirect endpoint.

### Evidence Collection — Analyst

1. Preserve the original events, timestamps and alert ID.
2. Export the linked flood events.
3. Record the source IP or IPs, requests per second, duration, target endpoint and the host's resource state.

### Investigation — Analyst

1. Determine whether the traffic was an authorized load test, a misbehaving client or a deliberate denial-of-service attempt.
2. Establish the impact: service degradation, failed legitimate requests or full outage.
3. Escalate confirmed or distributed denial of service to the SOC Lead.

### Containment — Lead / Admin

1. For a single source, record `block IP` with a 1800–3600 s timeout and confirm it after approval.
2. For distributed sources, note that blocking individual addresses is ineffective; raise the Security Group or an upstream mitigation with the provider instead.
3. Record every containment action, its reason, owner and timestamp.

### Remediation and Recovery — Admin / Host Owner

1. Confirm the host recovers once the traffic stops and monitor CPU, connections and error rates.
2. Enable or tighten rate-limiting on the flooded endpoint and enable caching for redirect responses where appropriate.
3. Confirm that normal service, logging and detection are functioning.

### Closure — Admin

1. Record the final findings, request rate, duration, impact and mitigation applied.
2. For an authorized load test, record the authorization and use the supported benign/false-positive disposition.
3. Document the containment action or the upstream mitigation, then close the alert as resolved.
4. Close the incident only when all closure criteria are met.

## 10. Scenario — Generic IDS signature / unusual DNS

**Rules:** `IDS-SIG-001` (HIGH) · `DNS-ANOMALY-001` (LOW)  
**Source:** custom IDS (`ids/live_ids_ips.py`), signatures from `ids/ids.yaml`

| Signature id | Really means | Follow |
|---|---|---|
| `9000001` | port scan | §6 |
| `9000002` | SSH brute force | §5 |
| `9000003` | SYN flood | §9 |
| `9000004` | DNS tunnelling | §10 (below) |
| `9000005` | unusual outbound | §11 |

### Triage — Analyst

1. Read the signature `id`, `msg`, `priority` and `category` on the linked event to identify which signature fired.
2. Map the signature to its scenario using the table above and open that playbook.
3. Check whether a dedicated alert already exists for the same source and window; the IDS is a second view of the same activity and must not be counted as a second attack.
4. For `9000004`, confirm the DNS trigger: a label longer than 50 characters, or more than 100 queries per minute from one host, and note the queried names.
5. For `9000004`, determine who is sending: the SOC host itself (outbound exfiltration, more serious) or an external source (probe, usually noise).

### Evidence Collection — Analyst

1. Preserve the original events, signature fields, timestamps and alert IDs.
2. Export the linked IDS events; for DNS, export the queried names and query rate.
3. Record the signature ID, message, source IP and, for DNS, the originating host, direction and resolver involved.
4. Record the matching rule alert for the same activity, where one exists, and keep both under one incident.

### Investigation — Analyst

1. Determine which scenario the signature really describes and apply that scenario's investigation steps.
2. For DNS, identify the queried domain and its reputation and check the process or user that generated the queries.
3. Check for a preceding compromise; tunnelling is a post-compromise behaviour.
4. Escalate any case where the SOC host is the DNS sender to the SOC Lead; treat it as suspected malware.

### Containment — Lead / Admin

1. Apply the containment decision of the mapped scenario's playbook and do not block twice for the same source.
2. For a host sending unusual DNS, record `isolate host` and investigate for malware or a tunnelling agent.
3. For a host receiving probe-like DNS, record `block IP` for the source where warranted and confirm it after approval.
4. For known-good resolver traffic, change the allow-list or threshold instead of blocking.
5. Record every containment action, its reason, owner and timestamp.

### Remediation and Recovery — Admin / Host Owner

1. Apply the mapped scenario's remediation.
2. For DNS tunnelling, remove the agent or reconfigure the application, block the domain at the resolver and tune the IDS thresholds if the traffic was legitimate.
3. Confirm that the suspicious queries stop and that normal service, logging and detection are functioning.

### Closure — Admin

1. Record the final findings, the signature that fired and the scenario it represents.
2. For authorized test traffic, record the authorization and use the supported benign/false-positive disposition.
3. When this alert duplicates a dedicated alert, close it inside that alert's incident rather than standalone.
4. Close the incident only when all closure criteria are met.

*Reproduce the DNS case with `attack-sim/dns-tunnel-sim.sh` (runs on the
instance).*

## 11. Scenario — Unusual outbound connection

**Rule:** `NET-OUTBOUND-001` (MEDIUM)  
**Source:** custom IDS signature `9000005`, from nftables `SOC_OUT:` log lines

### Triage — Analyst

1. Confirm the trigger: the host opened a connection to a destination port outside the allow-list (53, 80, 443, 123).
2. Identify the destination IP and port, and the process that opened it (`ss -tnp`, `lsof -i`).
3. Check the destination against known-good services and against any ticket for an approved change.
4. Review related events over the previous 30 minutes, including `DNS-ANOMALY-001`, `SSH-SUCCESS-001` and web alerts; outbound traffic is a classic post-compromise signal.

### Evidence Collection — Analyst

1. Preserve the original events, timestamps and alert ID.
2. Export the `SOC_OUT:` events.
3. Record the destination IP, destination port, owning process, user, connection duration, volume and traffic pattern.

### Investigation — Analyst

1. Determine whether the connection is legitimate egress, a mis-configured service or command-and-control or exfiltration.
2. Identify the process owner, its expected behaviour and whether that destination is part of it, and check the destination's reputation.
3. Escalate unexplained outbound connections to the SOC Lead, especially where a prior compromise exists.

### Containment — Lead / Admin

1. For a known-good service, update the egress allow-list instead of blocking; do not break legitimate egress.
2. For a suspicious or unexplained destination, record `block IP` for the destination and confirm it after approval.
3. For suspected command-and-control, record `isolate host` and involve the lead.
4. Record every containment action, its reason, owner and timestamp.

### Remediation and Recovery — Admin / Host Owner

1. Stop the offending process or service and reconfigure it to use an approved destination and port.
2. Confirm no further connections to the blocked destination after containment.
3. Review the host for the compromise that could have opened the connection; rebuild from the clean baseline when malware is confirmed.
4. Confirm that normal service, logging and detection are functioning.

### Closure — Admin

1. Record the final findings, the destination, owning process, impact and remediation actions.
2. For legitimate traffic, document the allow-list change and close the alert as resolved, or as a false positive with the authorization recorded.
3. For command-and-control or exfiltration, verify containment, process removal and host recovery before requesting closure.
4. Close the incident only when all closure criteria are met.

## 12. Recovery, closure and reporting (shared)

**Recovery checklist**
- [ ] Blocked source confirmed and (if temporary) tracked for its timeout.
- [ ] Legitimate traffic from other sources unaffected.
- [ ] No new accounts, keys, cron jobs, or modified configs on the host.
- [ ] Any disabled account reset with new credentials before re-enabling.

**Closure (alerts)**
- Benign → **FALSE POSITIVE** with a reason (only valid from `NEW`/`INVESTIGATING`).
- Handled → `CONTAINED` → **RESOLVED**.

**Closure (incidents)**
- Move `investigating → contained → resolved → closed`. **Only the admin closes
  an incident**; the analyst or lead prepares the closure record.
- Write a **root cause** and **lessons learned**; the platform computes TTC
  (time-to-contain) and TTR (time-to-resolve) from the timeline.

**Reporting**
- Every resolved incident can be exported to HTML/CSV from the Incidents page;
  archive the exported report under `docs/reports/`.

## 13. False positives and the second source

The allow-list (`rules/allowlist.yaml`, `/etc/mini-soc/allowlist.txt`) suppresses
known-benign sources (the analyst IP, the approved scanner). To demonstrate a
**false positive** deliberately, run approved test traffic from a second,
allow-listed source (a phone hotspot) and record why the alert was closed as
FALSE POSITIVE. See `docs/testing/second-source-ip.md`.

---

*Umbrella playbook. Edit this file and the per-rule playbooks in this directory,
then rebuild the dashboard (`npm run build` runs `sync-playbooks.mjs`).*
