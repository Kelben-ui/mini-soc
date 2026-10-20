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

   The same file holds the DVWA credentials the web scripts log in with
   (`DVWA_USER` / `DVWA_PASS`, default `admin` / `password`). `target.conf`
   should be in `.gitignore` — it changes whenever the instance restarts
   without an Elastic IP, and shouldn't be committed with a stale or shared
   IP.

2. Make scripts executable:

   ```bash
   chmod +x port-scan.sh ssh-brute-force.sh sqli-xss.sh scanner-ua.sh \
            recon-chain.sh outbound-conn.sh dns-tunnel-sim.sh
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

### `ssh-brute-force.sh`
Runs Hydra against SSH with a fixed username and password list. Stops on
first success (`-f`). Triggers the SSH brute-force rule (≥10 failures in
5 minutes) and, if the real password is reached, the login-success-after-
brute-force rule. Also expected to trigger `live_ids_ips.py`'s own
brute-force detection and iptables block — if it blocks your source
mid-test, you may need to clear that rule before re-running.

```bash
./ssh-brute-force.sh <EC2_PUBLIC_IP> testuser passlist.txt
```

### `sqli-xss.sh`
Sends attack payloads to DVWA on the target. Supports individual attack
types or `all`.

```bash
./sqli-xss.sh <EC2_PUBLIC_IP> sqli
./sqli-xss.sh <EC2_PUBLIC_IP> all
```

Attack types: `sqli`, `xss`, `cmdi`, `traversal`, `bruteforce`.

**Authenticated by default.** DVWA will not run a vulnerable module's code
until the request carries a logged-in session — an unauthenticated request
just bounces off `login.php`, so the payload never reaches the sink and never
appears in the access log. The script therefore:

1. `GET /dvwa/login.php` to prime a cookie jar and read the CSRF
   `user_token`;
2. `POST /dvwa/login.php` with `DVWA_USER`/`DVWA_PASS` from `target.conf`;
3. verifies the session actually reached `/dvwa/index.php` (DVWA answers 302
   for both good and bad passwords, so the status code alone proves nothing)
   and aborts loudly if login failed;
4. sends every payload with the session cookie.

`bruteforce` deliberately skips the authenticated session and re-fetches a
fresh `user_token` for each wrong-password attempt, since failed logins are
exactly what `WEB-BF-001` counts.

**Prerequisite:** DVWA must be initialised (`/dvwa/setup.php` → *Create /
Reset Database*, which creates `admin` / `password` by default). Security
level is set to **low** via the `security` cookie that DVWA hands out on the
first request, so no manual `/dvwa/security.php` step is needed.

### `scanner-ua.sh`
Sends requests with the User-Agents used by sqlmap / Nikto / Nmap / Gobuster.
This is what trips `scanner_user_agent` (WEB-SCAN-001) — the rule matches the
`User-Agent` string, so no valid exploit is needed.

```bash
./scanner-ua.sh <EC2_PUBLIC_IP>
```

### `recon-chain.sh`
Runs all four stages in sequence from one source: port scan → SQLi → XSS
→ SSH brute force. Used to test correlation (alerts from one src_ip
across 2+ categories within 30 minutes) and for the final live demo.

```bash
./recon-chain.sh <EC2_PUBLIC_IP>
```

Since web target and SSH target are now the same host, no separate
IP juggling is needed — the single EC2 public IP is used throughout.

Its SQLi/XSS stage calls `sqli-xss.sh`, so it inherits the DVWA login /
CSRF handling described above and needs no extra setup.

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

### HTTP flood — replay only, no script

`http_flood` (WEB-FLOOD-001) fires on ≥301 requests from one source within
60 seconds. There is deliberately **no** attack-sim script for it: sending
that volume from a laptop to an internet-facing EC2 instance is exactly the
kind of sustained/DoS-shaped traffic AWS restricts. It is a rate threshold
rather than a payload, so it is covered by the replay suite
(`detection/tests/replay_test.py`) and the synthetic nginx log in
`sample-data/`, which push >300 requests through the same rule.

## Known gaps / to confirm

- [x] Exact DVWA vulnerability page paths — confirmed against DVWA 1.x:
      `/dvwa/login.php`, `/dvwa/vulnerabilities/{sqli,xss_r,exec,fi,brute}/`.
      The login form needs a CSRF `user_token`; the low-security vuln pages
      need only the session cookie. Both are handled by `sqli-xss.sh`.
- [x] Whether DVWA session cookies / CSRF tokens need to be handled in
      `sqli-xss.sh` — yes; the script now logs in (fetching `user_token`) and
      replays the session on every payload. See the `sqli-xss.sh` section.
- [ ] Confirm sshd config on the instance has no rate-limiting or
      fail2ban that would throttle the brute-force test (separate from
      `live_ids_ips.py`'s own intentional blocking)
- [ ] Confirm timing (`-T4` on Nmap, sleep gaps in recon-chain) against
      the real internet path to AWS — adjust if latency is higher than
      a local lab would have been
- [x] Decide and document the second-source-IP method for the
      false-positive demo step (hotspot, VPN, or similar) — see
      `docs/testing/second-source-ip.md`
- [ ] Confirm whether `target.conf` should instead read an Elastic IP,
      to avoid updating it every time the instance restarts

> **Confirmed end-to-end (local WSL lab):** every `sqli-xss.sh` attack type was
> run against the local stack; the collector parsed the `soc` access log and the
> detection engine raised `WEB-SQLI-001`, `WEB-XSS-001`, `WEB-LFI-001`,
> `WEB-CMD-001`, `WEB-SCAN-001` and `WEB-BF-001`. This also closes the former
> "confirm each script's traffic produces the expected log lines" item for the
> web scripts. See `docs/testing/local-wsl-run.md`.

## Logging format

Each script appends one line per run to `attack-log.txt`:

```
<UTC timestamp> | <script:stage> | target=<ip> | user=<whoami>
```

This is the record used in `docs/testing/test-plan.md` to show which
rule was tested, when, and by whom.
