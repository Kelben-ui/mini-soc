# Demo Script — Mini SOC (EC2 Adapted)

This script adapts the original §8 demo for the single EC2 deployment.

## Prerequisites
- Completed `docs/testing/pre-session-checklist.md`
- Services active, DVWA security low
- target.conf configured

## Demo Flow (≈10-15 minutes)

1. **Intro** (dashboard)
   - Show Overview: threat level, active alerts, agent health.
2. **Recon** (Kali)
   - `sudo ./port-scan.sh $TARGET` → triggers NET-PORTSCAN-001
3. **Web attacks**
   - `./sqli-xss.sh $TARGET sqli` (WEB-SQLI-001)
   - `./sqli-xss.sh $TARGET xss` (WEB-XSS-001)
   - `./sqli-xss.sh $TARGET cmdi` (WEB-CMD-001)
   - `./sqli-xss.sh $TARGET traversal` (WEB-LFI-001)
   - `./scanner-ua.sh $TARGET` (WEB-SCAN-001)
4. **Web brute force**
   - `./sqli-xss.sh $TARGET bruteforce` (WEB-BF-001)
5. **SSH brute force + success**
   - `./ssh-brute-force.sh $TARGET testuser passlist.txt` (SSH-BF-001, SSH-SUCCESS-001)
6. **Host-originated**
   - On EC2: `./outbound-conn.sh 203.0.113.5 4444` (NET-OUTBOUND-001)
   - On EC2: `./dns-tunnel-sim.sh` (DNS-ANOMALY-001)
7. **Correlation**
   - `./recon-chain.sh $TARGET` → show chain (Attack Chains)
8. **Triage**
   - Alerts: status NEW → INVESTIGATING; linked events
9. **Containment**
   - Promote chain to incident; add block IP; confirm → helper adds to nftables; unblock
10. **Incident management**
   - Notes, evidence export, status flow, timeline, report export
11. **False positive demo**
   - Second source (hotspot) per `docs/testing/second-source-ip.md`; show benign below threshold/noisy suppressed

## Rehearsal Log
| Date (UTC) | Operator | Rehearsal # | Duration | Issues | Pass/Fail |
|---|---|---|---|---|---|
| | | 1 | | | [PENDING] |
| | | 2 | | | [PENDING] |
