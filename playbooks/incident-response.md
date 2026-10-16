# Mini SOC — Incident Response Playbook

> **Version:** 1.1 · **Deployment:** single Amazon EC2 instance (public
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

The Mini SOC runs as **one EC2 instance**. There is no separate firewall host:
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
open ──► investigating ──► contained ──► resolved ──► closed   (closing needs an analyst/lead role)
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
| WEB-BF-001 | Web login brute force | HIGH | ≥20 POST `/login` from one `src_ip` / 120 s | [`web-login-bruteforce.md`](web-login-bruteforce.md) | §8 |
| WEB-FLOOD-001 | HTTP flood | MEDIUM | ≥301 requests with status 301 / 60 s from one `src_ip` | [`http-flood.md`](http-flood.md) | §9 |
| SSH-BF-001 | SSH brute force | HIGH | ≥10 failed `ssh_login` / 300 s (per src→dst) | [`ssh-brute-force.md`](ssh-brute-force.md) | §5 |
| SSH-SUCCESS-001 | Login success after brute force | CRITICAL | successful `ssh_login` (correlated to a BF alert) | [`ssh-success-after-bruteforce.md`](ssh-success-after-bruteforce.md) | §5 |
| NET-PORTSCAN-001 | Port scan | MEDIUM | nftables/IDS: ≥20 distinct ports from one source | [`port-scan.md`](port-scan.md) | §6 |
| IDS-SIG-001 | Generic IDS signature | HIGH | IDS alert that is not a mapped kind (SSH-sig, SYN flood) | [`ids-signature.md`](ids-signature.md) | §10 |
| DNS-ANOMALY-001 | Unusual DNS activity | LOW | IDS DNS-tunnelling signature (long labels / high rate) | [`unusual-dns.md`](unusual-dns.md) | §10 |
| NET-OUTBOUND-001 | Unusual outbound connection | MEDIUM | host connects out to a port outside 53/80/443/123 | [`unusual-outbound.md`](unusual-outbound.md) | §11 |

## 5. Scenario — SSH brute force / successful login

**Rules:** `SSH-BF-001` (HIGH), `SSH-SUCCESS-001` (CRITICAL).
The IDS also raises its own SSH signature (`9000002`), which arrives as
`IDS-SIG-001` (§10) — the two are the same activity seen from two sources.

**Trigger.** ≥10 failed `ssh_login` events from one `src_ip` to the same
`dst_ip` within 300 s (auth.log). `SSH-SUCCESS-001` fires on a *successful*
login that the detection engine correlates to an open brute-force alert.

**Triage**

1. Confirm the failed-login burst and the targeted username(s). One account =
   targeted; several = password spraying.
2. **Check for a success on the same source.** If `SSH-SUCCESS-001` fired, treat
   this as a **suspected compromise**, not an attempt — escalate now.
3. Correlate: a prior `NET-PORTSCAN-001` from the same IP in the last 30 min is
   the classic recon → brute-force chain.

**Evidence**
- Export the linked `auth.log` events (failed attempts plus any success).
- Record: `src_ip`, target host (`soc-01`), targeted username(s), attempt count,
  window, whether a success occurred.
- If a success occurred, export the `SSH-SUCCESS-001` alert too and keep both
  under the same incident.

**Containment**
- Attempts only (no success): **Block IP** for the source (3600 s) once the
  threshold is confirmed and traffic is ongoing.
- Success occurred: **Block IP** for the source, then record **`disable
  account`** for the compromised username and reset its credentials +
  `authorized_keys` out-of-band. `SSH-SUCCESS-001` must go through full
  incident closure.

**Recovery**
- Confirm normal SSH from approved sources still works after the block.
- Confirm no new `authorized_keys`, users, or cron entries on the host.
- Longer term: disable password auth (`PasswordAuthentication no`) — see
  `infrastructure/ec2-soc/sshd_config`.

**Closure**
- Benign (e.g. an approved test IP) → **FALSE POSITIVE** with reason.
- Real attempt, no success → alert **RESOLVED**, incident `resolved` → `closed`.
- Success → incident closure with root cause, credential reset, lessons learned.

*Reproduce this scenario with `attack-sim/ssh-brute-force.sh` (see
`attack-sim/README.md`).*

## 6. Scenario — Network reconnaissance

**Rules:** `NET-PORTSCAN-001` (MEDIUM), `WEB-SCAN-001` (MEDIUM).

**Trigger**
- `NET-PORTSCAN-001`: a burst of connection attempts across many distinct
  destination ports from one source (nftables `SOC_DROP:`/`SOC_ACCEPT:` lines
  and/or the IDS `scan` signature `9000001`).
- `WEB-SCAN-001`: an HTTP request whose `User-Agent` matches a known scanner
  (sqlmap, nikto, nmap, gobuster).

**Triage**
1. Confirm the distinct-port count / the scanner UA string.
2. Correlate over the last 30 minutes: reconnaissance with **no** follow-on is
   often an authorised scan; recon **followed by** `WEB-SQLI-001`, `WEB-CMD-001`
   or `SSH-BF-001` from the same IP is stage 1 of an attack chain — promote the
   chain to an incident.
3. Check the source against the allow-list (analyst IP, approved scanner).

**Evidence**
- Export the scanned-port events / the scanner request lines.
- Record: `src_ip`, target, first/last seen, distinct port count or UA string.

**Containment**
- Standalone, low confidence → **monitor**, no block.
- Correlated with exploitation attempts → **Block IP** for the chain's source
  (1800 s is usually enough for pure recon; 3600 s if exploitation followed).

**Recovery / Closure**
- Benign → **FALSE POSITIVE** with reason.
- If part of a chain → close the **alert** as part of the parent incident, not
  standalone.
- Otherwise document the ports/UA and the duration, then **RESOLVED**.

## 7. Scenario — Web application attack (SQLi / XSS / command injection / LFI)

**Rules:** `WEB-SQLI-001` (HIGH), `WEB-XSS-001` (MEDIUM), `WEB-CMD-001` (HIGH),
`WEB-LFI-001` (HIGH). All match decoded URI/body content on DVWA/Nginx traffic.

**Trigger**
- `WEB-SQLI-001`: `' or `, `" or `, `union select`, `select `, ` from `,
  `sleep(`, `--`, `/*`.
- `WEB-CMD-001`: `; id`, `; whoami`, `| id`, `| whoami`, `&& id`, `&& whoami`.
- `WEB-LFI-001`: `../`, `/etc/passwd`, `php://`.
- `WEB-XSS-001`: `<script`, `javascript:`, `onerror=`, `onload=`.

**Triage**
1. Identify which rule(s) fired and the exact token that matched.
2. Read the decoded URI/body from the linked event and confirm it is a real
   exploit attempt, not a false positive (a legitimate apostrophe in a form
   field can trip the SQLi pattern).
3. Check the HTTP status returned. A `200` on a DVWA endpoint that echoes
   database output or a command result means the exploit likely **succeeded**.
4. Correlate with `WEB-SCAN-001` / `NET-PORTSCAN-001` (the scan that found the
   endpoint) and `WEB-BF-001` (credential discovery) in the last 30 minutes.

**Evidence**
- Export the linked Nginx request events (with the decoded payload).
- If exploitation looks successful, capture the DVWA response itself, not just
  the log line, and attach it to the incident.
- Record: `src_ip`, endpoint, payload, HTTP status, and whether data/execution
  was observed.

**Containment**
- Isolated scanner/UA hit only → monitor.
- Confirmed exploitation attempt → **Block IP** for the source and promote to an
  incident.
- Command injection or LFI with evidence of success → **Block IP** immediately,
  record **`isolate host`**, involve a lead, and treat `soc-01` as potentially
  compromised (there is no container to stop — this is a host-level review).

**Recovery**
- Review the web root and configs for unexpected files or modifications.
- Reset DVWA to a known-clean state before resuming testing.
- If credentials were exposed, note them for rotation.

**Closure**
- Benign (own testing from an approved IP) → **FALSE POSITIVE** with reason.
- Real attempt, no success → **RESOLVED** with root cause (e.g. "unpatched DVWA
  `id` parameter") and lessons learned.
- Success → full incident closure, signed off by a lead.

## 8. Scenario — Web login brute force

**Rule:** `WEB-BF-001` (HIGH).

**Trigger:** ≥20 `POST /login` requests from one `src_ip` within 120 s.

**Triage**
1. Confirm the POST burst and the target path.
2. Look for a successful login from the same IP after the burst (check the
   Nginx `status` on later requests).
3. Correlate with `WEB-SCAN-001` and `NET-PORTSCAN-001`.

**Evidence / Containment / Recovery / Closure**
- Export the login POST events; record attempt count and whether a login
  succeeded.
- Ongoing attempt → **Block IP** (3600 s).
- Successful credential use → treat as compromise: **Block IP** + record
  **`disable account`** for the web account and reset it.
- Benign → **FALSE POSITIVE**; otherwise **RESOLVED** / incident closure.

## 9. Scenario — HTTP flood

**Rule:** `WEB-FLOOD-001` (MEDIUM).

**Trigger:** ≥301 requests with HTTP status `301` from one `src_ip` within 60 s.

**Note:** there is deliberately **no** attack-sim script for this — sending that
volume from a laptop at an internet-facing instance is the kind of sustained
traffic AWS restricts. It is covered by `detection/tests/replay_test.py` and the
synthetic log in `sample-data/`.

**Triage**
1. Confirm the request rate and status code; check whether the host is
   CPU/connection saturated (`top`, `ss -s`).
2. Correlate for a preceding scan (a flood is often automated abuse of a
   discovered redirect endpoint).
3. Distinguish a single misbehaving client from a distributed flood.

**Evidence**
- Export the flood events; record `src_ip`, requests/second, and duration.

**Containment**
- Single source → **Block IP** (1800–3600 s).
- Distributed sources → blocking individual IPs is ineffective; note it and
  consider the Security Group / an upstream AWS mitigation as the real control.

**Recovery / Closure**
- Confirm the host recovers once traffic stops. Document rate/duration and close
  as **RESOLVED**.

## 10. Scenario — Generic IDS signature / unusual DNS

**Rules:** `IDS-SIG-001` (HIGH), `DNS-ANOMALY-001` (LOW).

**Trigger**
- `IDS-SIG-001`: an IDS alert the collector could not map to a specific kind —
  e.g. the SSH-brute-force signature (`9000002`) or a SYN flood (`9000003`).
- `DNS-ANOMALY-001`: the IDS `dns` signature (`9000004`) — high DNS rate and/or
  oversized labels, i.e. suspected tunnelling.

**Triage**
1. Check the signature `msg`/`category` on the event to see which IDS signature
   fired.
- `IDS-SIG-001` for the SSH signature usually means the same activity that
  produced `SSH-BF-001`; use §5 and avoid double-counting it as a second attack.
- For SYN-flood-shaped `IDS-SIG-001`, treat like §9.
- For `DNS-ANOMALY-001`, check the queried name pattern (long/random labels) and
  whether it originates from the host itself or an external source.

**Evidence / Containment / Recovery / Closure**
- Export the IDS events; record the signature id/msg and the source.
- `IDS-SIG-001` → follow the mapped scenario's containment.
- `DNS-ANOMALY-001`: if the host is *sending* unusual DNS, investigate for
  malware/exfiltration (record **`isolate host`**); if it is receiving probe-like
  DNS, **Block IP** if warranted.
- Close as **RESOLVED** or, for approved test traffic, **FALSE POSITIVE**.

*Reproduce the DNS case with `attack-sim/dns-tunnel-sim.sh` (runs on the
instance).*

## 11. Scenario — Unusual outbound connection

**Rule:** `NET-OUTBOUND-001` (MEDIUM).

**Trigger:** the instance opens an outbound connection to a port **outside** the
allow-list (53/80/443/123). The nftables `SOC_OUT:` rule logs the SYN; the IDS
outbound signature (`9000005`) carries it into the SOC.

**Triage**
1. Identify the destination IP/port and the process that opened it
   (`ss -tnp`, `lsof -i`).
2. Decide whether it is legitimate egress the allow-list should cover, a
   mis-configured service, or command-and-control / exfiltration.

**Evidence**
- Export the `SOC_OUT:` events; record `dst_ip`, `dst_port`, and the owning
  process.

**Containment**
- Known-good service → update the egress allow-list (do **not** block).
- Suspicious/unexplained → **Block IP** the destination and record
  **`isolate host`** pending investigation.

**Recovery / Closure**
- Confirm no further connections to the destination after the block.
- Document the root cause; close **RESOLVED** (or **FALSE POSITIVE** for
  legitimate traffic).

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
- Move `investigating → contained → resolved → closed`. Closing requires an
  analyst/lead role.
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
