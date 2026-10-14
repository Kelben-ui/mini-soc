# Mini SOC Platform — Rule Test Plan

Owner: Member 6. Purpose: verify every required detection rule fires
correctly, with few false positives, and that deduplication and
correlation work as specified.

Each row is filled in during Week 4 onward, as Member 3's rules go live.
Do not mark Pass until the alert has actually been observed on the
dashboard/API with the correct severity.

## How to run these tests

The lab is now one internet-facing EC2 instance, not an isolated
multi-VM network, so the pre-check is different:

1. Confirm the Security Group only has the ports you intend open
   (22, 80, plus your own IP for dashboard/API access) before testing.
2. Confirm the EC2 instance is running and reachable at its public IP:
   `TARGET=<EC2_PUBLIC_IP>` — [FILL IN: use the actual Elastic IP/public
   DNS once assigned, since a stopped/restarted instance without an
   Elastic IP gets a new public IP each time].
3. Run the matching script from `attack-sim/` from your **local Kali
   VM**, against `$TARGET`.
4. Check the dashboard (or `GET /api/alerts`) for the expected alert
   within a reasonable time of the rule's detection window.
5. Record the actual result and mark Pass/Fail. Note the actual `src_ip`
   recorded — it will be your home/laptop's public IP, not a clean lab
   IP, and may change between sessions if your ISP rotates it.
6. Background internet scanning may hit the box once 22/80 are open —
   if an unexpected alert appears from an unfamiliar IP during a test
   window, note it separately rather than mixing it into your own
   test's result.
7. For any Fail, file it as an issue and note it under "Known issues"
   at the bottom.

## Rule test matrix

Scripts below assume `$TARGET` is the EC2 instance's public IP, run
from the local Kali VM over the internet — **not** a `192.168.10.x` lab
address as in earlier drafts of the attack-sim scripts. See
`attack-sim/README.md` for the updated target-validation approach.

| # | Rule ID | Test scenario | Script used | Expected alert (severity) | Actual result | Pass/Fail |
|---|---|---|---|---|---|---|
| 1 | SSH brute force | ≥10 failed SSH logins, same src_ip, 5 min | `ssh-brute-force.sh $TARGET testuser passlist.txt` | HIGH | | |
| 2 | Login success after brute force | Success from an IP with an open brute-force alert | Same run as #1 (passlist ends with real password) | CRITICAL | | |
| 3 | Web login brute force | ≥20 POSTs to DVWA login, same src_ip, 2 min | `sqli-xss.sh $TARGET bruteforce` | HIGH | | |
| 4 | SQL injection | Decoded URI/body matches SQLi pattern | `sqli-xss.sh $TARGET sqli` | HIGH | | |
| 5 | Cross-site scripting | `<script`, event handler, or `javascript:` in URI/body | `sqli-xss.sh $TARGET xss` | MEDIUM | | |
| 6 | Command injection | `;`, `\|`, `&&` + shell command on DVWA exec page | `sqli-xss.sh $TARGET cmdi` | HIGH | | |
| 7 | Directory traversal / LFI | `../`, `/etc/passwd`, `php://` in parameters | `sqli-xss.sh $TARGET traversal` | HIGH | | |
| 8 | Scanner user agent | sqlmap/nikto/nmap/gobuster in User-Agent | `scanner-ua.sh $TARGET` | MEDIUM | | |
| 9 | HTTP flood | >300 requests, same src_ip, 1 min | Replay only — no live script (AWS restricts sustained/DoS-shaped traffic). `detection/tests/replay_test.py` + `sample-data/` drive the same threshold. | MEDIUM | | |
| 10 | Port scan | ≥20 distinct dest ports, same src_ip, 1 min | `port-scan.sh $TARGET` | MEDIUM | | |
| 11 | IDS signature (custom IDS) | Any alert from `ids/live_ids_ips.py`; severity mapped from the signature | `port-scan.sh $TARGET` or `ssh-brute-force.sh …` (both feed the IDS) | Mapped | | |
| 12 | Unusual outbound connection | Server opens connection to a port not on the allow-list | `outbound-conn.sh <dest_ip> <port>` — run **on the instance**, not from Kali | MEDIUM | | |
| 13 | Unusual DNS activity | Over-long subdomain (or high query rate) from the host | `dns-tunnel-sim.sh` — run **on the instance**, not from Kali | LOW | | |

Rules #12 and #13 are host-originated (they watch what the SOC instance
itself sends), so their attack-sim scripts run on the EC2 instance rather
than from the local Kali VM.  The IDS reads them from the nftables
`SOC_OUT:` journal lines (#12) and a raw `AF_PACKET` DNS sniffer (#13), so
they no longer depend on Suricata or a separate firewall host.

## AWS-specific notes

- Rules #12 and #13 (unusual outbound, unusual DNS) assumed Suricata
  sitting inline on fw-01, watching all traffic. With a single
  internet-facing EC2 instance there is no separate firewall host; the
  custom IDS now provides both sources (nftables `SOC_OUT:` logging and a
  raw DNS sniffer), so the rules are **kept, not descoped**.
  - nftables only sees traffic that actually arrives at the host — the
    Security Group drops everything else, so the two must be kept in sync.
- Because the EC2 instance is reachable from the whole internet once
  22/80 are open, expect some background noise (automated scanners,
  bots) hitting the box between test sessions. This is a known and
  normal side effect, not a bug — just don't let it contaminate your
  controlled test results.

## Deduplication test

| Test | Expected result | Actual | Pass/Fail |
|---|---|---|---|
| Run `ssh-brute-force.sh` twice in a row against the same target within the 5-min window | Second run updates the **same** open alert's `count` and `last_seen`, does not create a new alert | | |

## Correlation test

| Test | Expected result | Actual | Pass/Fail |
|---|---|---|---|
| Run `recon-chain.sh <web-01>` (port scan → SQLi → XSS → SSH brute force from one source, within 30 min) | All resulting alerts grouped under one `chain_id`; dashboard suggests promoting to one incident | | |

## Response-action (block) test

The custom IDS is detection-only; blocking is a separate, human-confirmed
step (task 4.7). Test it end to end:

| Test | Expected result | Actual | Pass/Fail |
|---|---|---|---|
| From a finding, record a `block IP` response action targeting the offending src_ip, then confirm it in the dashboard | Backend runs `/usr/local/sbin/soc-block` via sudo; `nft list set inet filter blocklist` shows the IP; the action's `status` becomes `executed`; an audit-log row is written | | |
| Click **Unblock** on that action | `nft list set inet filter blocklist` no longer shows the IP; `status` becomes `unblocked` | | |
| Try to block an allow-listed IP (in `/etc/mini-soc/allowlist.txt`) | Refused (HTTP 403) — nothing is added to the set | | |
| Try to block a non-IPv4 target | Refused (HTTP 400) — nothing is added to the set | | |
| Call `/api/actions/{id}/execute` without `confirm: true` | Refused (HTTP 400) — the block never runs without confirmation | | |

## Known issues

[FILL IN as testing proceeds — log any rule that consistently fails,
false-positives, or needs threshold tuning, with the date and rule ID.]

## Attack-sim coverage

Every rule now has a trigger path:

| Rule | Trigger |
|---|---|
| SSH brute force / login success | `ssh-brute-force.sh` |
| Web login brute force | `sqli-xss.sh $TARGET bruteforce` |
| SQLi / XSS / cmd injection / traversal | `sqli-xss.sh $TARGET <type>` |
| Scanner user agent | `scanner-ua.sh` |
| HTTP flood | replay only (`detection/tests/replay_test.py`) |
| Port scan / IDS signature | `port-scan.sh` |
| Unusual outbound | `outbound-conn.sh` (on the instance) |
| Unusual DNS | `dns-tunnel-sim.sh` (on the instance) |

HTTP flood deliberately has no live script: against an internet-facing
EC2 instance a >300/min burst resembles the DoS traffic AWS restricts.
It is a rate threshold with no payload, so the replay suite and
`sample-data/` cover it. The two host-originated rules (#12, #13) run
`outbound-conn.sh` / `dns-tunnel-sim.sh` on the instance itself, since
the IDS watches the host's own `SOC_OUT:` journal lines and DNS
queries rather than inbound Kali traffic.

Before each session, run the pre-flight checks in
`docs/testing/pre-session-checklist.md`.
