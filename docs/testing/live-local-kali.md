# Live simulation runbook — Kali (attacker) → Windows/WSL2 SOC

**Audience:** operator running a live, end-to-end demo of the Mini SOC.
**Attacker:** Kali VM (**bridged** onto the LAN).
**Target/SOC:** the full stack in **WSL2 `Ubuntu-24.04`** on the Windows host.

> This is the *live* companion to
> [`local-wsl-run.md`](local-wsl-run.md) (which records the platform test) and
> [`wsl-local/README.md`](wsl-local/README.md) (the repeatable harness). Here the
> attacker is a **separate Kali machine on the LAN**, not an in-host netns.

---

## 0. Topology

```
Kali VM (bridged, LAN)              Windows host                    WSL2 Ubuntu-24.04
  192.168.1.x  ──────────────────►  192.168.1.41 ──portproxy──►     172.22.54.155
  attacker                           :80 :443 :22                  nginx :80/:443
                                     + firewall allow rules        backend :8000
                                                                   collector :9000
                                                                   sshd :22 (added here)
```

Because the SOC services listen **inside WSL2's NAT**, Kali cannot reach them
directly. Windows **portproxy** forwards `192.168.1.41:{80,443,22}` into the WSL2
guest, and Windows Firewall rules allow those inbound ports. Kali is **bridged**,
so it already routes to `192.168.1.41` with no extra configuration.

### Placeholders

| Name | How to obtain | Example |
|---|---|---|
| `WIN_IP` | `ipconfig` on Windows (Wi-Fi adapter) | `192.168.1.41` |
| `WSL_IP` | `wsl -d Ubuntu-24.04 -u root -- hostname -I` (first address) | `172.22.54.155` |
| `<lab-admin-pw>` | the dashboard admin password (this lab: `localtest-admin-1`) | `localtest-admin-1` |

**`WSL_IP` changes on every WSL restart.** Re-check it and re-run the portproxy
step (Phase 2) after any reboot.

---

## 1. Pre-flight (Windows + WSL)

### Terminal A — Windows PowerShell (Administrator)

```powershell
ipconfig | Select-String -Pattern 'IPv4'
```

Expect the Wi-Fi adapter line, e.g. `IPv4 Address . . . : 192.168.1.41`. Record as
**WIN_IP**.

```powershell
wsl -d Ubuntu-24.04 -u root -- hostname -I
```

Expect a line like `172.22.54.155 172.22.48.1`. The **first** address is
**WSL_IP**.

### Terminal B — WSL (root)

```bash
wsl -d Ubuntu-24.04 -u root
```

Then, inside WSL:

```bash
systemctl is-active nginx soc-backend soc-collector soc-detection soc-agent mini-soc-ids postgresql mariadb
```

**Expected (8 × `active`):**

```
active
active
active
active
active
active
active
active
```

> **Note on unit names.** The current units are `soc-backend`, `soc-collector`,
> `soc-detection`, `soc-agent`, `mini-soc-ids`. `mini-soc-backend` /
> `mini-soc-collector` are **legacy names** (see `LEGACY_UNITS` in
> `deploy/install.sh`) and do **not** exist — querying them yields
> `could not be found` and `journalctl` says `-- No entries --`. That is expected,
> not a failure.

```bash
ss -ltnp | grep -E ':(80|443|8000|9000|5432|3306)'
```

Expect listeners on all six ports (nginx on `0.0.0.0:80/:443`; backend
`127.0.0.1:8000`; collector `127.0.0.1:9000`; postgres `127.0.0.1:5432`;
mariadb `127.0.0.1:3306`).

```bash
cat /etc/mini-soc/allowlist.txt; echo "lines=$(wc -l </etc/mini-soc/allowlist.txt)"
```

Expect the file to print nothing and `lines=0` — i.e. **Kali traffic will be
analysed** (an allowlisted source would be skipped).

If any service is not `active`, re-provision (idempotent) as root — **no `sudo`
needed when you are already root**:

```bash
cd /root/mini-soc && deploy/install.sh
```

> The running stack lives at **`/root/mini-soc`** — every systemd unit's
> `WorkingDirectory` and `ExecStart` point there, and only root can traverse
> `/root`. Your *editing* checkout is the Windows mount
> (`/mnt/c/Users/-kelsey-/Desktop/mini-soc`) and is what you push from; changes
> there do not reach the running stack until `deploy/update.sh` (or
> `install.sh`) runs. To sync quickly:
> `git -C /root/mini-soc fetch origin main && git -C /root/mini-soc reset --hard origin/main`.

---

## 2. Install & enable `sshd` in WSL (for the SSH rules)

WSL2 ships **no `sshd`** (only `openssh-client`), so `SSH-BF-001` /
`SSH-SUCCESS-001` cannot fire until you add it. Confirmed: port 22 is closed and
there is no `/etc/ssh/sshd_config`.

### Terminal B — WSL as root

```bash
apt-get update && apt-get install -y openssh-server
```

Expect the run to end with `Setting up openssh-server ...`.

```bash
mkdir -p /run/sshd

cat >/etc/ssh/sshd_config.d/99-mini-soc-lab.conf <<'EOF'
Port 22
PermitRootLogin no
PasswordAuthentication yes
KbdInteractiveAuthentication no
UsePAM yes
EOF
```

Create a **throwaway low-privilege account** with a password that the
brute-force wordlist in Phase 4.7 does **not** contain (so failures are followed
by one success):

```bash
useradd -m -s /bin/bash svcuser
echo 'svcuser:Sunshine123' | chpasswd
systemctl enable --now ssh
systemctl is-active ssh
```

Expect `active`.

```bash
ss -ltnp | grep ':22'
```

Expect `LISTEN ... 0.0.0.0:22` (or `*:22`).

Confirm sshd is writing to the auth log the collector agent tails:

```bash
ssh -o StrictHostKeyChecking=no -o BatchMode=yes svcuser@127.0.0.1 true; echo "exit=$?"
tail -2 /var/log/auth.log
```

Expect `Permission denied (publickey,password).` and `exit=255` (BatchMode
suppressed the password; password auth is still enabled), and a fresh
`Failed password`/`Connection closed` line with today's date.

> `rsyslog` is active on this host and `/var/log/auth.log` exists, so
> `collector/parsers/auth_parser.py` receives real `sshd` lines.

---

## 3. Windows port forwarding (80, 443, 22)

### Terminal A — PowerShell as Administrator

```powershell
$WSL=(wsl -d Ubuntu-24.04 -u root -- hostname -I).Trim().Split()[0]
"WSL_IP=$WSL"

netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=80  connectaddress=$WSL connectport=80
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=443 connectaddress=$WSL connectport=443
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=22  connectaddress=$WSL connectport=22

New-NetFirewallRule -DisplayName "mini-soc 80"  -Direction Inbound -Action Allow -Protocol TCP -LocalPort 80
New-NetFirewallRule -DisplayName "mini-soc 443" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 443
New-NetFirewallRule -DisplayName "mini-soc 22"  -Direction Inbound -Action Allow -Protocol TCP -LocalPort 22
```

Verify:

```powershell
netsh interface portproxy show all
```

Expect three `v4tov4` rows:

```
0.0.0.0         80          172.22.54.155   80
0.0.0.0         443         172.22.54.155   443
0.0.0.0         22          172.22.54.155   22
```

```powershell
Test-NetConnection 192.168.1.41 -Port 80  -InformationLevel Quiet
Test-NetConnection 192.168.1.41 -Port 443 -InformationLevel Quiet
Test-NetConnection 192.168.1.41 -Port 22  -InformationLevel Quiet
```

Expect three × `True`.

> **Reboot/reconnect:** `WSL_IP` changes whenever WSL restarts. Re-run the
> `$WSL=...` line and the three `portproxy ... add` lines (`add` overwrites). If a
> `Test-NetConnection` is `False`, see the troubleshooting branch at the end.

---

## 4. Baseline the SOC, then confirm reachability from Kali

### Terminal B — WSL as root

```bash
cd /root/mini-soc/docs/testing/wsl-local
./verify.sh baseline
```

Expect a line like `baseline (events alerts): <N> <M>`, written to
`~/.verify-baseline`. Phase 6 diffs against it — record the `alerts` figure.

### Terminal C — Kali

```bash
curl -s -o /dev/null -w 'dvwa=%{http_code}\n' http://192.168.1.41/dvwa/login.php
curl -sk -o /dev/null -w 'dash=%{http_code}\n' https://192.168.1.41/
```

Expect `dvwa=200` and `dash=200`. **If both hang or fail, stop and fix Phase 3** —
nothing downstream will work.

> A request to the bare root `http://192.168.1.41/` returns **403** — nginx
> refuses a directory listing at `/var/www/`. That is normal; always use a real
> path such as `/dvwa/login.php`.

Then prepare the attack scripts:

```bash
git clone https://github.com/Kelben-ui/mini-soc.git ~/mini-soc   # or scp the folder
cd ~/mini-soc/attack-sim
cp target.conf.example target.conf
chmod +x *.sh          # belt-and-braces; exec bits are now tracked in git
```

If you already have the clone, update it instead — an old checkout predates the
exec-bit fix and `./scanner-ua.sh` will fail with `Permission denied`:

```bash
cd ~/mini-soc && git pull
cd attack-sim && chmod +x *.sh
```

Edit `target.conf` (keep the **quotes** — the scripts match the value exactly):

```bash
ALLOWED_TARGET="192.168.1.41"
DVWA_SCHEME="http"
DVWA_USER="admin"
DVWA_PASS="password"
```

---

## 5. Attack phases (run on Kali)

Each block lists the command, the expected **Kali-side** output, then the
expected **alert**.

### 5.1 Port scan → `NET-PORTSCAN-001` (MEDIUM)

```bash
./port-scan.sh 192.168.1.41
# equivalent bounded scan:
#   nmap -sS -Pn -p 1-1024 --min-rate 500 192.168.1.41
```

Expect nmap to report open `22/tcp`, `80/tcp`, `443/tcp`.

> **Do not** use `-p- --min-rate 1000` here: on this link it produces ~130k
> firewall drop lines in seconds and trips the SYN-flood signature. Keep the range
> bounded (≥ 20 distinct ports to exceed the port-scan threshold).

**Alert:** `NET-PORTSCAN-001`, `src_ip = 192.168.1.x`, count ≥ 1.
Also expect `IDS-SIG-001` when the IDS signature fires.

### 5.2 Scanner User-Agent → `WEB-SCAN-001` (MEDIUM)

```bash
./scanner-ua.sh 192.168.1.41
```

Expect a handful of requests sent with `sqlmap` / `nikto` / `nmap` / `gobuster`
style User-Agents.

**Alert:** `WEB-SCAN-001`.

### 5.3 SQLi + XSS (authenticated) → `WEB-SQLI-001`, `WEB-XSS-001`

`sqli-xss.sh` takes **two** arguments — `<target_ip> <attack_type>`:

```bash
./sqli-xss.sh 192.168.1.41 sqli
./sqli-xss.sh 192.168.1.41 xss
```

Expect the script to log in, print that the session reached `/dvwa/index.php`,
then fire payloads.

**Alerts:** `WEB-SQLI-001` (HIGH) and `WEB-XSS-001` (MEDIUM), `src_ip = 192.168.1.x`.

> Available attack types: `sqli`, `xss`, `cmdi`, `traversal`, `bruteforce`,
> `all`. `./sqli-xss.sh 192.168.1.41 all` runs every one of them in a single
> pass — the quickest way to exercise all the web rules.

### 5.4 Web login brute force → `WEB-BF-001` (HIGH)

```bash
./sqli-xss.sh 192.168.1.41 bruteforce
```

Expect many `POST /dvwa/login.php` requests with wrong credentials (fresh CSRF
token per attempt).

**Alert:** `WEB-BF-001`, count ≈ number of attempts (threshold 20 / 120 s).

### 5.5 Command injection → `WEB-CMD-001` (HIGH)

```bash
./sqli-xss.sh 192.168.1.41 cmdi
```

(Or by hand: the rule matches `;whoami`, `;id`, `&&cat`, etc., with or without a
space — e.g. `curl -s 'http://192.168.1.41/dvwa/vulnerabilities/exec/?ip=127.0.0.1;id&Submit=Submit' -o /dev/null`.)

**Alert:** `WEB-CMD-001` (HIGH).

### 5.6 Path traversal / LFI → `WEB-LFI-001` (HIGH)

```bash
./sqli-xss.sh 192.168.1.41 traversal
```

**Alert:** `WEB-LFI-001` (HIGH).

### 5.7 SSH brute force → `SSH-BF-001` (HIGH, threshold 10 / 300 s)

Create a wordlist that **excludes** `Sunshine123`:

```bash
printf 'password\n123456\nadmin\nroot\nletmein\ntoor\nqwerty\nsunshine\nmonkey\niloveyou\nwrongpass\nnope\n' > pw.txt
./ssh-brute-force.sh 192.168.1.41 svcuser pw.txt
```

Expect the tool to report repeated authentication failures.

**Alert:** `SSH-BF-001`, `action = ssh_login`, `outcome = failure`,
`src_ip = 192.168.1.x`, `dst_ip = 172.22.54.155`, count ≥ 10.

### 5.8 SSH success after brute force → `SSH-SUCCESS-001` (CRITICAL)

```bash
sshpass -p 'Sunshine123' ssh -o StrictHostKeyChecking=no svcuser@192.168.1.41 'whoami'
```

Expect `svcuser`.

**Alert:** `SSH-SUCCESS-001` (CRITICAL) — fires on the first successful
`ssh_login`, pairing the success with the preceding failures.

### 5.9 On-box network rules (run in **WSL**, not Kali)

```bash
# NET-OUTBOUND-001 — a new outbound connection is logged as SOC_OUT:
curl -s https://example.com -o /dev/null

# DNS-ANOMALY-001 — an unusual DNS query
dig @8.8.8.8 this-is-a-very-long-anomalous-dns-label-xxxxxxxx.example.com
```

**Alerts:** `NET-OUTBOUND-001` and `DNS-ANOMALY-001` (if enabled in your rule
set).

---

## 6. Verify (WSL) and view the dashboard

### Terminal B — WSL as root

```bash
cd /root/mini-soc/docs/testing/wsl-local
./verify.sh delta
```

> The harness lives under `/root`, which only root can traverse, so run it as
> root (`wsl -d Ubuntu-24.04 -u root`). No password argument is needed: if
> `/etc/mini-soc/lab-creds.env` exists it is sourced automatically. Otherwise
> pass them inline: `SOC_PASS=<lab-admin-pw> ./verify.sh delta`.

Expect an event/alert count line showing counts now vs the Phase 4 baseline, then
a `--- latest alerts ---` list with `rule_id`, severity and `src_ip` for each
rule (including `SSH-BF-001`, `SSH-SUCCESS-001`, `NET-PORTSCAN-001`,
`WEB-SQLI-001`):

```
before (events alerts): 12345 67
after  (events alerts): 12489 78
--- latest alerts ---
  #78 SSH-SUCCESS-001        sev=CRITICAL src=192.168.1.x     Login success after brute force
  #77 SSH-BF-001             sev=HIGH     src=192.168.1.x     SSH brute force
  ...
```

`verify.sh query [log_type]` lists the newest **events**, optionally filtered by
`log_type` — the valid types are the log sources, not rule IDs:

```bash
./verify.sh query auth
./verify.sh query nginx_access
./verify.sh query firewall
```

Expect rows for the `auth` (SSH) and `nginx_access` (web) traffic you generated.

To inspect the **alerts** by rule ID, the `delta` output above already lists the
newest 8 with their `rule_id`; the dashboard (below) shows the full list.

### Dashboard (Terminal A — PowerShell)

```powershell
Start-Process "https://192.168.1.41/"
```

Log in:

```
Username: admin
Password: localtest-admin-1
```

Expect the alerts list to show the HIGH/CRITICAL rules above, newest first.

### Live detection telegraph (optional, very demo-friendly)

```bash
# Terminal B: WSL
journalctl -kf | grep --line-buffered SOC_DROP
```

Re-run the Phase 5.1 scan from Kali: `SOC_DROP:` lines appear live in WSL as Kali
probes ports, proving detection is wired end to end.

---

## 7. Teardown / reset

### Kali

```bash
rm -f pw.txt /tmp/dvwa_cookie
```

### WSL as root

```bash
userdel -r svcuser
rm -f /etc/ssh/sshd_config.d/99-mini-soc-lab.conf
systemctl disable --now ssh
```

### Windows PowerShell (Administrator)

```powershell
netsh interface portproxy reset
Get-NetFirewallRule -DisplayName "mini-soc *" | Remove-NetFirewallRule
```

---

## 8. Troubleshooting — Kali cannot reach the SOC

1. **All ports closed / ping fails** → `WSL_IP` changed. Re-run the `$WSL=...`
   line and the three `portproxy ... add` lines (Phase 3).
2. **Still closed** → confirm the portproxy listener exists:
   ```powershell
   netstat -ano | Select-String ':80|:443|:22'
   ```
   Expect `0.0.0.0:80 LISTENING` etc., owned by PID 4 (`System`).
3. **Windows blocks some ports** → the rule may be bound to the wrong profile.
   From Kali run `nmap -Pn -p80,443,22 192.168.1.41`; if only some open, re-add
   the rules with `-Profile Any`.
4. **Kali cannot route to Windows** → confirm bridged networking:
   `ip a` (expect `192.168.1.x/24`) and `ping 192.168.1.41`.
5. **Reaches Windows, WSL refuses** → inside WSL `ss -ltnp`; if nginx is not on
   `0.0.0.0:80`, re-check `deploy/nginx/mini-soc.conf` and re-run
   `deploy/install.sh`.

---

## 9. Collector `422` on `/ingest` — fixed

Before the fix you could see occasional lines in the collector journal:

```
INFO: 127.0.0.1:<port> - "POST /ingest HTTP/1.1" 422 Unprocessable Entity
```

**Cause (now fixed).** The nginx **error** log contains multi-line PHP FastCGI
entries:

```
2026/10/20 10:56:10 [error] 1769#1769: *19 FastCGI sent in stderr: "PHP message: PHP Warning: ... in /var/www/...
Stack trace:
#0 /var/www/dvwa/login.php(8): dvwaDatabaseConnect()
#1 {main}
  thrown in /var/www/dvwa/... on line 569" while reading response header from upstream, ...
```

The agent's tailer splits physical lines, so the continuation lines (`Stack
trace:`, `#0 ...`) did not match the parser's header regex and parsed to `None`.
When a 2-second batch contained only continuation lines the collector returned
`422` and the agent treated the 4xx as "handled" — the lines were dropped.

**Fix (agent-side multi-line join).**

- `agent.yaml` file sources accept an optional `multiline_start` regex. For
  `error.log` it is `'^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \['`.
- `agents/log_agent/tailer.py` folds non-matching lines onto the preceding
  match (joined with `\n`), and releases a held entry once an idle poll shows no
  further bytes — so a trailing entry still ships.
- `collector/parsers/nginx_error_parser.py` compiles its pattern with
  `re.DOTALL`, so `message` can span the joined newlines (without it, `$` never
  matched and the joined entry was rejected).
- The collector now logs a sample of the offending line on every 422, so any
  future mismatch is diagnosable instead of silent.

Verified live: an injected multi-line entry arrives as a single `nginx_error`
event whose `message` keeps the stack trace, and the collector returns `200`
with no 422.
