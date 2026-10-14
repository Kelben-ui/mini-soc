# Testing Results (EC2 End-to-End)

## Scope
End-to-end validation of detection rules against replay/sample data and live EC2 deployment.

## Phase 5 Gate: Replay Test
- Command: `cd /home/ubuntu/mini-soc && PYTHONPATH=/home/ubuntu/mini-soc .venv/bin/python detection/tests/replay_test.py`
- Result: REPLAY TEST PASSED
- Rules fired: 13/13 (WEB-SQLI-001, WEB-LFI-001, WEB-CMD-001, WEB-XSS-001, DNS-ANOMALY-001, NET-PORTSCAN-001, IDS-SIG-001, SSH-BF-001, WEB-BF-001, WEB-SCAN-001, WEB-FLOOD-001, SSH-SUCCESS-001, NET-OUTBOUND-001)
- Deduplication: holds (alerts updated, not duplicated)
- Chain formation: 1 chain formed across related alerts
- Detection window: within expected timing (<10s after event injection)

## Rule Summary (post Phase 1 alignment)
All 13 rules have `category:` and `mitre:` present. IDS mappings aligned (ids_alert, status key). nginx keys frozen.

## Live EC2 Run — 13 Rules Matrix
See `docs/testing/live-runbook.md` for commands. Fill the "Actual result" cells after running.

| # | Rule ID | Script | Expected alert (severity) | Detection time (s) | Actual result | Pass/Fail | Notes/False positives |
|---|---|---|---|---|---|---|---|
| 1 | SSH-BF-001 | `ssh-brute-force.sh $TARGET testuser passlist.txt` | HIGH | — | [PENDING] | [PENDING] | |
| 2 | SSH-SUCCESS-001 | same run | CRITICAL | — | [PENDING] | [PENDING] | |
| 3 | WEB-BF-001 | `sqli-xss.sh $TARGET bruteforce` | HIGH | — | [PENDING] | [PENDING] | |
| 4 | WEB-SQLI-001 | `sqli-xss.sh $TARGET sqli` | HIGH | — | [PENDING] | [PENDING] | |
| 5 | WEB-XSS-001 | `sqli-xss.sh $TARGET xss` | MEDIUM | — | [PENDING] | [PENDING] | |
| 6 | WEB-CMD-001 | `sqli-xss.sh $TARGET cmdi` | HIGH | — | [PENDING] | [PENDING] | |
| 7 | WEB-LFI-001 | `sqli-xss.sh $TARGET traversal` | HIGH | — | [PENDING] | [PENDING] | |
| 8 | WEB-SCAN-001 | `scanner-ua.sh $TARGET` | MEDIUM | — | [PENDING] | [PENDING] | |
| 9 | WEB-FLOOD-001 | replay only | MEDIUM | — | [PENDING] | [PENDING] | |
| 10 | NET-PORTSCAN-001 | `port-scan.sh $TARGET` | MEDIUM | — | [PENDING] | [PENDING] | |
| 11 | IDS-SIG-001 | any IDS alert | HIGH | — | [PENDING] | [PENDING] | |
| 12 | NET-OUTBOUND-001 | on-box: `outbound-conn.sh 203.0.113.5 4444` | MEDIUM | — | [PENDING] | [PENDING] | |
| 13 | DNS-ANOMALY-001 | on-box: `dns-tunnel-sim.sh` | LOW | — | [PENDING] | [PENDING] | |

## Additional Tests
- Deduplication: run ssh-brute-force twice in 5 min → same alert count increments. [PENDING]
- Correlation (chain): `recon-chain.sh $TARGET` → one chain_id across categories. [PENDING]
- Block/unblock + safety: block IP (confirmed), unblock; allow-listed 403; non-IPv4 400; no-confirm 400. [PENDING]

## Security Test
See `docs/testing/security-test.md` (offline: 11/11 PASS; EC2 port scan [PENDING]).
