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
| 1 | SSH brute force | ≥10 failed SSH logins, same src_ip, 5 min | `ssh-bruteforce.sh $TARGET testuser passlist.txt` | HIGH | | |
| 2 | Login success after brute force | Success from an IP with an open brute-force alert | Same run as #1 (passlist ends with real password) | CRITICAL | | |
| 3 | Web login brute force | ≥20 POSTs to DVWA login, same src_ip, 2 min | `web-attacks.sh $TARGET bruteforce` | HIGH | | |
| 4 | SQL injection | Decoded URI/body matches SQLi pattern | `web-attacks.sh $TARGET sqli` | HIGH | | |
| 5 | Cross-site scripting | `<script`, event handler, or `javascript:` in URI/body | `web-attacks.sh $TARGET xss` | MEDIUM | | |
| 6 | Command injection | `;`, `\|`, `&&` + shell command on DVWA exec page | `web-attacks.sh $TARGET cmdi` | HIGH | | |
| 7 | Directory traversal / LFI | `../`, `/etc/passwd`, `php://` in parameters | `web-attacks.sh $TARGET traversal` | HIGH | | |
| 8 | Scanner user agent | sqlmap/nikto/nmap/gobuster in User-Agent | [FILL IN: not yet in web-attacks.sh — add a curl call with `-A "sqlmap/1.8"` as a new case] | MEDIUM | | |
| 9 | HTTP flood | >300 requests, same src_ip, 1 min | [FILL IN: not yet scripted — add a loop sending >300 rapid GETs. Note: against a real internet-facing EC2 instance, be conservative here — this can resemble a DoS test, which AWS restricts. Keep it brief and well under any sustained-flood threshold.] | MEDIUM | | |
| 10 | Port scan | ≥20 distinct dest ports, same src_ip, 1 min | `port-scan.sh $TARGET` | MEDIUM | | |
| 11 | IDS signature (live_ids_ips.py) | Any IDS alert from the custom daemon, severity mapped from its own classification | [FILL IN: confirm exactly what `live_ids_ips.py` flags — per the earlier report it covers Nmap and SSH brute-force detection via journalctl; confirm if it has other signatures too] | Mapped | | |
| 12 | Unusual outbound connection | Server opens connection to a port not on an allow-list | [FILL IN: with no separate fw-01, this rule needs a new source — e.g. the host's own outbound iptables/journalctl, or drop this rule if it no longer has a natural log source in the single-instance design. Raise with the team.] | MEDIUM | | |
| 13 | Unusual DNS activity | Very long subdomains or high query rate from one host | [FILL IN: same concern as #12 — Suricata normally handled DNS inspection; confirm whether this rule is still feasible without it, or should be dropped as an Advanced item given the architecture change] | LOW | | |

## AWS-specific notes

- Rules #12 and #13 (unusual outbound, unusual DNS) assumed Suricata
  sitting inline on fw-01, watching all traffic. With a single
  internet-facing EC2 instance and no separate firewall host, these two
  rules may need to be **descoped or re-justified** — flag this
  explicitly at your next check-in rather than letting it surface at
  the demo.
- Because the EC2 instance is reachable from the whole internet once
  22/80 are open, expect some background noise (automated scanners,
  bots) hitting the box between test sessions. This is a known and
  normal side effect, not a bug — just don't let it contaminate your
  controlled test results.

## Deduplication test

| Test | Expected result | Actual | Pass/Fail |
|---|---|---|---|
| Run `ssh-bruteforce.sh` twice in a row against the same target within the 5-min window | Second run updates the **same** open alert's `count` and `last_seen`, does not create a new alert | | |

## Correlation test

| Test | Expected result | Actual | Pass/Fail |
|---|---|---|---|
| Run `recon-chain.sh <web-01>` (port scan → SQLi → XSS → SSH brute force from one source, within 30 min) | All resulting alerts grouped under one `chain_id`; dashboard suggests promoting to one incident | | |

## Known issues

[FILL IN as testing proceeds — log any rule that consistently fails,
false-positives, or needs threshold tuning, with the date and rule ID.]

## Attack-sim coverage gaps

The following rules have no attack-sim script yet (see `[FILL IN]`
markers above) and need scripts added before they can be tested:
- Scanner user agent
- HTTP flood
- IDS signature (depends on your custom IDS's detection logic)
- Unusual outbound connection
- Unusual DNS activity

[FILL IN: once your custom IDS's detection logic for IDS-signature,
outbound, and DNS rules is known, come back and write the matching
attack-sim scripts and update this plan.]
