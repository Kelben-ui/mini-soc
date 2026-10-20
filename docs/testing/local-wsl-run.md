# Local (WSL2) firewall / nginx / DVWA test run

**Date:** 2026-10-20
**Environment:** Windows host → **WSL2 `Ubuntu-24.04`** (Ubuntu 24.04.5, kernel 6.18, systemd 255)
**Target:** the EC2 lab reproduced locally (`/root/mini-soc`), attacker = a network
namespace on the same WSL host.
**Why local:** the EC2 instance is stopped; WSL2 runs the same OS as the lab AMI
(Ubuntu 24.04), so the systemd units, nginx, nftables, PHP-FPM, MariaDB and
PostgreSQL all behave the same way.

> This run tested the **platform plumbing** (firewall → nginx → DVWA →
> agent → collector → detection → API). It is not a substitute for the
> internet-facing EC2 run, but it exercises the same code paths.
>
> The runnable harness that came out of this exercise lives in
> [`wsl-local/`](wsl-local/README.md) (`setup-attacker.sh`, `run-tests.sh`,
> `verify.sh`). All three defects found here were fixed in the same change-set.

---

## 1. How the local lab is laid out

| Piece | Where |
|---|---|
| Target host | WSL2 Ubuntu-24.04, repo at `/root/mini-soc` |
| nginx | :80 (DVWA, `default_server`) and :443 (dashboard + `/api` proxy) |
| DVWA | `/var/www/dvwa`, MariaDB `dvwa` (security level **low**) |
| SOC stack | `soc-backend`, `soc-collector`, `soc-detection`, `soc-agent`, `mini-soc-ids`, `postgresql` |
| Firewall | nftables `/etc/nftables.conf` (`SOC_DROP:` / `SOC_OUT:` logging) |
| Attacker | netns **`atk`**, address `10.99.0.2`, veth pair to host `10.99.0.1` |

The netns attacker matters: loopback traffic is accepted unconditionally by the
ruleset (`iif "lo" accept`), so attacking `127.0.0.1` cannot exercise the
firewall. A veth pair gives real interface traffic with an external-looking
source IP, exactly like Kali → EC2.

### Reproduce / restart

```bash
# 1. copy repo into WSL's ext4 (not /mnt/c)
# 2. provision the stack
sudo MINI_SOC_APP_DIR=/root/mini-soc DOMAIN=localhost bash /root/mini-soc/deploy/install.sh
# 3. attacker namespace
sudo bash /root/mini-soc/docs/testing/wsl-local/setup-attacker.sh
# 4. smoke tests
sudo APP_DIR=/root/mini-soc bash /root/mini-soc/docs/testing/wsl-local/run-tests.sh all
```

The namespace does **not** persist across a WSL restart — re-run
`setup-attacker.sh` after a reboot.

---

## 2. Firewall test

### 2.1 Port exposure (external view)

```bash
ip netns exec atk nmap -Pn -sS -p- --min-rate 1000 10.99.0.1
```

Result:

```
22/tcp  closed ssh
80/tcp  open   http
443/tcp open   https
(65532 filtered tcp ports)
```

**PASS** — only 80 and 443 are reachable. Port 22 shows *closed* rather than
open because WSL has no sshd (the lab AMI does); the firewall rule for 22 is
present and correct.

### 2.2 Host view

`ss -tlnp` confirms only nginx is exposed; PostgreSQL/collector/backend bind to
`127.0.0.1` (5432, 8000, 9000) and MariaDB to `127.0.0.1:3306` — i.e. the
services are listening but **not** reachable through the firewall.

### 2.3 Drop + logging path

The same scan produced **65,000+ `SOC_DROP` journal lines**, e.g.:

```
SOC_DROP: IN=veth-soc ... SRC=10.99.0.2 DST=10.99.0.1 ... DPT=7494 ... SYN
```

These are parsed by the collector as `firewall` events (category `network`,
action `drop`) and are the raw material for the port-scan rule.

### 2.4 Port-scan detection

The template IDS signature fired from the attack traffic:

```
{"signature": "MINI-SOC Port Scan Detected", "count": 20, "src_ip": "10.99.0.2"}
{"signature": "MINI-SOC SYN Flood Detected",  "count": 100, "src_ip": "10.99.0.2"}
```

and the correlation rule over the parsed events produced dashboard alerts
**`NET-PORTSCAN-001`** and **`IDS-SIG-001`** for `10.99.0.2` (alerts #3, #4).

**PASS.**

> **Operational note.** A full `-p-  --min-rate 1000` scan against a local veth
> link is fast enough to flood the pipeline (~130k drop lines in seconds) and to
> trip the SYN-flood signature. `run-tests.sh` therefore uses a bounded range
> (`-p 1000-1023 -T4 --max-retries 1`), which still exceeds the 20-distinct-ports
> threshold without the flood.

---

## 3. nginx test

`run-tests.sh nginx` runs all of the following; every check passes.

| Check | Result |
|---|---|
| `nginx -t` | **PASS** |
| nginx service active | **PASS** |
| Listeners | `0.0.0.0:80`, `0.0.0.0:443` (+ IPv6) |
| Dashboard `GET /` | **200** |
| Backend `GET :8000/health` | **`{"status":"ok"}`** |
| API auth guard (`/api/stats`, no token) | **403** |
| Security headers | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Content-Security-Policy` all present |
| `soc` log format | `... [iso=...] "GET /dvwa/login.php HTTP/1.1" 200 1354 "" "curl/8.5.0" body=` |
| HTTP→HTTPS redirect | `301 → https://localhost/` for `Host: localhost` |
| DVWA site | `/dvwa/`, `/dvwa/login.php`, `/dvwa/setup.php` → 302 / 200 / 200 |
| DVWA→MariaDB | 4 tables in schema `dvwa` |

**PASS.**

Notes:

- The backend's health endpoint is on the backend port (`:8000/health`); nginx
  only proxies `/api/`, so `https://host/health` is served by the dashboard SPA
  and `/api/health` is a 404. `run-tests.sh` checks the backend directly.
- `http://127.0.0.1/` (bare IP) returns **403**, because the redirect server in
  `mini-soc.conf` is `server_name $DOMAIN` and the DVWA server is
  `default_server`. With `DOMAIN=localhost` only that Host name matches. On the
  lab EC2 `DOMAIN` is a real name, so this is a local-only artifact.

---

## 4. DVWA test

### 4.1 Reachability and setup

`/dvwa/login.php` → 200; login as `admin` / `password`; security level **low**.
The login form requires a CSRF `user_token`; the vulnerability pages (at low
security) require only the session cookie.

### 4.2 Detection results

All web rules are exercised by `attack-sim/sqli-xss.sh`, which now logs in
first (see §5.4):

| Rule | Trigger used | Alert |
|---|---|---|
| `WEB-SQLI-001` | `id=1' OR 1=1-- -` | ✅ #6 (HIGH) |
| `WEB-XSS-001` | `name=<script>alert(1)</script>` | ✅ #8 (MEDIUM) |
| `WEB-LFI-001` | `page=../../../../etc/passwd` | ✅ #5 (HIGH) |
| `WEB-SCAN-001` | sqlmap / Nikto / Nmap / gobuster User-Agents | ✅ #7 (MEDIUM) |
| `WEB-BF-001` | 25 failed POSTs to `/dvwa/login.php` in <120 s | ✅ #9 (HIGH) |
| `WEB-CMD-001` | `ip=127.0.0.1;whoami` | ✅ #10 (HIGH) |
| `NET-PORTSCAN-001` | nmap ≥20 ports | ✅ #3 (MEDIUM) |
| `IDS-SIG-001` | IDS signature event | ✅ #4 (MEDIUM) |

Every web alert carried `src_ip = 127.0.0.1` and the correct severity; the
network alerts carried `src_ip = 10.99.0.2`. Alert counts grow on each new
attack run (`create_or_update_alert` updates the open alert for the same
rule + source rather than duplicating it).

---

## 5. Defects found — and the fixes applied

Three real defects surfaced. All are fixed in this change-set.

### 5.1 nginx error-log timezone bug — **blocked all detection on a non-UTC host**

`collector/parsers/nginx_error_parser.py` parsed nginx's error timestamp
(`2026/10/20 09:58:42`, written in **host local time, no offset**) and then did
`ts_dt.replace(tzinfo=timezone.utc)` — i.e. it *claimed local time was UTC*.

On this host (`Africa/Lagos`, **WAT = UTC+1**) that stored every `nginx_error`
event **one hour in the future**:

```
raw:     2026/10/20 09:58:42
stored:  2026-10-20T10:58:42+01:00   # == 09:58:42Z, but the true instant is 08:58:42Z
```

Because `detection/engine/engine.py` anchors its window on the **newest**
event (`latest_event.timestamp`), that future-dated row pushed the window an
hour ahead of real time, so genuinely-new attack events fell *outside* the
window and `run_detection` skipped them. Symptom: **no alerts at all**, even
though the raw log lines and parsed events were perfect. The bug is invisible
on the lab EC2, which runs UTC.

**Fix:** interpret the naive timestamp as local time and normalise to UTC —
`ts_dt.astimezone(timezone.utc)`.

**Regression guard:** `collector/tests/test_nginx_error_parser.py` adds a
`TZ=Africa/Lagos` test (expects `13:32:07Z`, the old code produced `14:32:07Z`),
a `TZ=UTC` test, and a "never ahead of wall clock" assertion. Verified failing
on the old code and passing on the fix.

### 5.2 `install.sh` / nginx `log_format soc` duplication

On a host whose `/etc/nginx/nginx.conf` is the captured
`infrastructure/ec2-soc/nginx/nginx.conf` (which defines `log_format soc` in the
`http` block), `install.sh` re-rendered `deploy/nginx/mini-soc.conf` — which
*also* defined `log_format soc`. nginx then failed with
`duplicate "log_format" name "soc"`, and `install.sh` aborted at `nginx -t`
before installing nftables or restarting services.

The two repo files disagreed about where the format lives:

| File | `log_format` | `access_log ... soc` |
|---|---|---|
| `deploy/nginx/mini-soc.conf` (installer template) | ~~defines it~~ | uses it |
| `infrastructure/ec2-soc/nginx/mini-soc.conf` (snapshot) | — | uses it |
| `infrastructure/ec2-soc/nginx/nginx.conf` (snapshot, "OS package") | defines it | — |

**Fix:** `infrastructure/ec2-soc/nginx/nginx.conf` is the **single owner** of
`log_format soc` (matching `docs/lab-setup.md`). `deploy/install.sh` now:

1. installs `nginx.conf` if `soc` is undefined, and
2. fails loudly if `soc` is defined in `sites-enabled` (the old broken state),
3. then `nginx -t` guards before proceeding.

The duplicate block was removed from `deploy/nginx/mini-soc.conf`, so the
installer is safe on both a fresh host and the snapshot host.

### 5.3 Windows checkout line endings

The repo was checked out on Windows, so `attack-sim/*.sh` and `deploy/*.sh`
had **CRLF** endings and failed inside WSL with `$'\r': command not found`.

**Fix:** the root `.gitattributes` already pins `*.sh text eol=lf`, so a fresh
clone on Windows gets LF. The new `docs/testing/wsl-local/*.sh` follow the same
rule. For an existing CRLF checkout, `sed -i 's/\r$//' *.sh` once.

### 5.4 The web rules did not match what DVWA/the simulator actually send

Found while exercising the rules (§4):

1. **`WEB-BF-001` pinned `details.uri: /login`.** That is the dashboard's
   client-side SPA route — it never reaches nginx. DVWA's login is
   `/dvwa/login.php` and its brute-force exercise posts to
   `/dvwa/vulnerabilities/brute/`, so the rule could not match DVWA at all.
   **Fix:** match the real DVWA paths (regex), still keyed on `POST` +
   `group_by: src_ip`, threshold 20 / 120 s.
2. **`WEB-CMD-001` required the metacharacter *and* a space** (`"; id"`),
   but `attack-sim/sqli-xss.sh` sends `;whoami` (no space) and the rule also
   missed `&&cat /etc/passwd`.
   **Fix:** a single regex `[;&|]+\s*(whoami|id|cat|uname|ls|nc|curl|wget|bash|sh|python|ping|sleep)\b`.
3. **The evaluator ANDed multiple `regex` patterns** in one rule, so a rule
   with two alternatives (`/login.php` *or* `/brute`) could never match while
   `contains` used `any` (OR). **Fix:** `detection/engine/evaluator.py` now
   treats the `regex` list as alternatives too, mirroring `contains`.
4. **`sqli-xss.sh` had no session** — it posted to the vulnerability pages
   unauthenticated, so DVWA returned `302 → login.php` and never ran the
   payload. **Fix:** the script now logs in (fetching the login CSRF
   `user_token`), verifies the session reached `index.php` (DVWA answers 302
   for both good and bad passwords, so the status code proves nothing), and
   replays the cookie on every payload. Credentials come from `target.conf`
   (`DVWA_USER` / `DVWA_PASS`). The `bruteforce` mode deliberately uses a
   throwaway session with fresh tokens per attempt.

**Regression guard:** `detection/tests/test_web_rules.py` feeds real
DVWA-shaped events through `matches_rule` / `get_threshold_events` for every
web rule; `detection/tests/replay_test.py`'s brute-force fixture now uses
`/dvwa/login.php`.

---

## 6. Verdict

| Area | Result |
|---|---|
| Firewall (exposure, drop+log, port-scan alert) | **PASS** |
| nginx (config, TLS, proxy, headers, `soc` format, DVWA vhost) | **PASS** |
| DVWA (reachable, DB connected, low security) | **PASS** |
| Detection end-to-end (web + network rules, authenticated) | **PASS** |
| Non-UTC timezone bug | **fixed** + regression test (5.1) |
| Rule/simulator mismatches | **fixed** + rule-contract tests (5.4) |
| Installer/nginx config conflict | **fixed** (5.2) |
| Windows line endings | **fixed** via `.gitattributes` (5.3) |

All ten alerts, the full event inventory (`firewall`, `auth`, `nginx_access`,
`nginx_error`, `mini_soc_ids`) and the agent heartbeat were confirmed through
the dashboard API. The harness reports **24/24 checks passing**.

### Follow-ups — status

| # | Follow-up | Status |
|---|---|---|
| 1 | Fix `nginx_error_parser.py` + non-UTC test | ✅ done (5.1) |
| 2 | Reconcile the `soc`/`log_format` files | ✅ done (5.2) |
| 3 | Align `WEB-CMD-001` with the simulator | ✅ done (5.4) |
| 4 | Point `WEB-BF-001` at DVWA's real login path | ✅ done (5.4) |
| 5 | Authenticated mode in `sqli-xss.sh` | ✅ done (5.4) |
| 6 | `.gitattributes` for shell endings | ✅ already present (5.3) |
| 7 | Checked-in repeatable harness | ✅ `docs/testing/wsl-local/` |
