# Live EC2 Runbook (Phase 9)

## Prerequisites
- EC2 instance running with Elastic IP
- Kali VM with mini-soc repo
- DVWA security level low; services up; analyst IP allowlisted

## Setup
```bash
TARGET=<your-EC2-Elastic-IP>
cd ~/mini-soc/attack-sim
cp target.conf.example target.conf
sed -i "s/203.0.113.10/$TARGET/" target.conf
printf 'wrongpass1\nwrongpass2\nwrongpass3\nwrongpass4\nwrongpass5\nwrongpass6\nwrongpass7\nwrongpass8\nwrongpass9\nwrongpass10\nrealpassword\n' > passlist.txt
chmod +x *.sh
```

## Pre-flight
Complete `docs/testing/pre-session-checklist.md`.

## 9.1: Run the 13 rules
Record injection/alert timestamps in `docs/testing/results.md`.

| # | Rule | Command | Expected |
|---|---|---|---|
| 1 | SSH-BF-001 | `./ssh-brute-force.sh $TARGET testuser passlist.txt` | HIGH |
| 2 | SSH-SUCCESS-001 | same run (ends with real pw) | CRITICAL |
| 3 | WEB-BF-001 | `./sqli-xss.sh $TARGET bruteforce` | HIGH |
| 4 | WEB-SQLI-001 | `./sqli-xss.sh $TARGET sqli` | HIGH |
| 5 | WEB-XSS-001 | `./sqli-xss.sh $TARGET xss` | MEDIUM |
| 6 | WEB-CMD-001 | `./sqli-xss.sh $TARGET cmdi` | HIGH |
| 7 | WEB-LFI-001 | `./sqli-xss.sh $TARGET traversal` | HIGH |
| 8 | WEB-SCAN-001 | `./scanner-ua.sh $TARGET` | MEDIUM |
| 9 | WEB-FLOOD-001 | replay only | MEDIUM |
| 10 | NET-PORTSCAN-001 | `sudo ./port-scan.sh $TARGET` | MEDIUM |
| 11 | IDS-SIG-001 | from 1/10 | mapped |
| 12 | NET-OUTBOUND-001 | **on box**: `./outbound-conn.sh 203.0.113.5 4444` | MEDIUM |
| 13 | DNS-ANOMALY-001 | **on box**: `./dns-tunnel-sim.sh` | LOW |

## 9.1: Extra
- Dedup: run #1 twice in 5 min → count increments.
- Chain: `./recon-chain.sh $TARGET` → one chain_id.
- Block: record+confirm block IP; nft shows; unblock; allow-listed 403; non-IPv4 400; no-confirm 400.

## 9.2: Port scan
```bash
nmap -Pn -sS -p- --min-rate 1000 $TARGET
```
Expect only 22,80 (+443). Also `ss -tlnp` on box.

## 9.4: Rehearsals
Follow `docs/demo-script.md` twice. Record in the log table there.

## 9.5: Reports
Export HTML/CSV from the demo incident in Incidents page → save to `docs/reports/`.
