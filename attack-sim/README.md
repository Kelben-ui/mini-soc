# attack-sim

Controlled attack scripts for the Mini SOC Platform. **Use only against
your own EC2 instance.**

The platform now runs as a single AWS EC2 instance (web target, SSH
target, and the full SOC stack combined), attacked from a local Kali VM
over the public internet — not an isolated lab network. Because the
target is a real internet IP rather than a fixed `192.168.10.0/24`
range, every script validates against a single configured target
instead of a CIDR range.

## Rules of engagement

- Only run these against **your own EC2 instance's public IP**, as set
  in `target.conf`. Never scan or attack any other AWS resource, IP, or
  domain — this is what keeps testing within AWS's self-testing
  allowance for resources you own.
- Keep activity brief and non-sustained — avoid anything that resembles
  a flood/DoS test (see rule #9 in the test plan).
- The Security Group should expose only the ports you intend (22, 80;
  dashboard/API restricted to your own IP) — verify before each session.
- Every run is logged to `./attack-log.txt` (timestamp, script, target,
  user) — don't delete this file, since it's part of the evidence trail
  for the test plan.
- Since the box is internet-facing, expect occasional unrelated
  background traffic from real internet scanners once 22/80 are open.
  That's expected noise, not a sign something's broken.

## Setup

1. Copy the target config and set it to your EC2 instance's current
   public IP (or Elastic IP, if assigned):

   ```bash
   cp target.conf.example target.conf
   # edit target.conf: ALLOWED_TARGET="<your EC2 public IP>"
   ```

   `target.conf` should be in `.gitignore` — it changes whenever the
   instance restarts without an Elastic IP, and shouldn't be committed
   with a stale or shared IP.

2. Make scripts executable:

   ```bash
   chmod +x port-scan.sh ssh-bruteforce.sh web-attacks.sh recon-chain.sh \
            outbound-conn.sh dns-tunnel-sim.sh
   ```

3. Create a password list for the brute-force script (never reuse these
   credentials anywhere else, and never commit this file):

   ```bash
   printf "wrongpass1\nwrongpass2\nwrongpass3\nwrongpass4\nwrongpass5\n\
   wrongpass6\nwrongpass7\nwrongpass8\nwrongpass9\nwrongpass10\n\
   wrongpass11\nrealpassword\n" > passlist.txt
   ```

Every script now reads `ALLOWED_TARGET` from `target.conf` and refuses
to run if the `<target_ip>` argument doesn't match it exactly — this
replaces the old CIDR-range check, which doesn't apply to an arbitrary
internet target.

## Scripts

### `port-scan.sh`
Runs an Nmap SYN scan against the configured target. Triggers the
port-scan detection rule (≥20 distinct ports in 1 minute) when run with
fast timing.

```bash
sudo ./port-scan.sh <EC2_PUBLIC_IP>
```

### `ssh-bruteforce.sh`
Runs Hydra against SSH with a fixed username and password list. Stops on
first success (`-f`). Triggers the SSH brute-force rule (≥10 failures in
5 minutes) and, if the real password is reached, the login-success-after-
brute-force rule. Also expected to trigger `live_ids_ips.py`'s own
brute-force detection and iptables block — if it blocks your source
mid-test, you may need to clear that rule before re-running.

```bash
./ssh-bruteforce.sh <EC2_PUBLIC_IP> testuser passlist.txt
```

### `web-attacks.sh`
Sends attack payloads to DVWA on the target. Supports individual attack
types or `all`.

```bash
./web-attacks.sh <EC2_PUBLIC_IP> sqli
./web-attacks.sh <EC2_PUBLIC_IP> all
```

Attack types: `sqli`, `xss`, `cmdi`, `traversal`, `bruteforce`.

**Prerequisite:** DVWA security level must be set to **low**
(`/dvwa/security.php`). If DVWA enforces session cookies or CSRF tokens,
the script needs updating to capture and replay them — check this once
DVWA is live and update this README with the working approach.

### `recon-chain.sh`
Runs all four stages in sequence from one source: port scan → SQLi → XSS
→ SSH brute force. Used to test correlation (alerts from one src_ip
across 2+ categories within 30 minutes) and for the final live demo.

```bash
./recon-chain.sh <EC2_PUBLIC_IP>
```

Since web target and SSH target are now the same host, no separate
IP juggling is needed — the single EC2 public IP is used throughout.

### `outbound-conn.sh` (run **on the instance**)
Opens a TCP connection to a destination port outside the allow-list
(53/80/443/123). The `SOC_OUT` nftables rule logs the new outbound
connection, which triggers the `unusual_outbound` (NET-OUTBOUND-001)
rule. This is the host-originated half of the IDS, so it runs on the
EC2 instance rather than from Kali.

```bash
./outbound-conn.sh <dest_ip> [dest_port]   # e.g. 203.0.113.5 4444
```

### `dns-tunnel-sim.sh` (run **on the instance**)
Sends DNS lookups with an over-long label (60 characters, above the
default `IDS_DNS_MAX_LABEL` of 50) — the shape of DNS tunnelling. The IDS
sniffs the queries on UDP/53 and raises `unusual_dns` (DNS-ANOMALY-001).

```bash
./dns-tunnel-sim.sh [count]                # default 5 lookups
```

Both scripts expect the query/connection to fail (the destination is a
reserved address / non-existent domain) — that is fine, the packet has
already left the host and been logged before it fails.

## Known gaps / to confirm

- [ ] Exact DVWA vulnerability page paths (can vary by DVWA version)
- [ ] Whether DVWA session cookies / CSRF tokens need to be handled in
      `web-attacks.sh`
- [ ] Confirm sshd config on the instance has no rate-limiting or
      fail2ban that would throttle the brute-force test (separate from
      `live_ids_ips.py`'s own intentional blocking)
- [ ] Confirm each script's traffic produces the expected log lines for
      the collector's parsers
- [ ] Confirm timing (`-T4` on Nmap, sleep gaps in recon-chain) against
      the real internet path to AWS — adjust if latency is higher than
      a local lab would have been
- [ ] Decide and document the second-source-IP method for the
      false-positive demo step (hotspot, VPN, or similar) — see
      `docs/architecture.md` Section 4
- [ ] Confirm whether `target.conf` should instead read an Elastic IP,
      to avoid updating it every time the instance restarts

## Logging format

Each script appends one line per run to `attack-log.txt`:

```
<UTC timestamp> | <script:stage> | target=<ip> | user=<whoami>
```

This is the record used in `docs/testing/test-plan.md` to show which
rule was tested, when, and by whom.
