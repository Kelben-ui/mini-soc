# Demo script — Mini SOC end-to-end walkthrough

A ~15-minute live demonstration of the full detection → alerting → correlation →
investigation → response loop on the EC2 lab, driven by the attack-sim scripts.

- **Audience:** assessor / reviewer, non-local to the build.
- **Presenters:** two people ideally — **Operator** (drives Kali, attacks) and
  **Analyst** (drives the dashboard). One person can do both, but the split
  makes the "attack happens elsewhere / analyst only sees the signal" story
  land.
- **Narrative:** a single external attacker (`203.0.113.66`-style, in reality
  the operator's public IP) probes the host, exploits the web app, then brute
  forces SSH and succeeds. The platform raises individual alerts, correlates them
  into one **chain**, promotes that to an **incident**, and the analyst
  **contains** the source with a real `block IP` action. A short second-source
  segment shows a benign source *not* alerting (false-positive control).

> **Safety.** Only ever point the scripts at **your own** instance. Run
> [`docs/testing/pre-session-checklist.md`](testing/pre-session-checklist.md)
> immediately before every rehearsal and the live run. The attack-sim scripts
> refuse to run unless the target matches `ALLOWED_TARGET` in
> `attack-sim/target.conf`.

---

## Roles and windows

| Window | Operator (Kali) | Analyst (dashboard) |
|---|---|---|
| Pre-flight | checklist, `target.conf`, `passlist.txt` | log in, open **Overview** |
| 0:00–0:03 | port scan | call out the port-scan alert |
| 0:03–0:06 | SQLi / XSS / cmdi / traversal | show the WEB-* alerts |
| 0:06–0:09 | SSH brute force (+ success) | show SSH-BF-001 then SSH-SUCCESS-001 |
| 0:09–0:12 | (standby) | open the **chain**, promote to **incident** |
| 0:12–0:14 | (standby) | record `block IP`, `nft` verify |
| 0:14–0:15 | hotspot benign traffic | show the second source does not alert |

---

## Pre-flight (~1 min before the audience arrives)

Both people:

```text
docs/testing/pre-session-checklist.md   # tick every box
```

Operator, on the Kali box:

```bash
cd mini-soc/attack-sim
cat target.conf                       # ALLOWED_TARGET = the lab public IP
chmod +x port-scan.sh ssh-brute-force.sh sqli-xss.sh scanner-ua.sh \
         recon-chain.sh outbound-conn.sh dns-tunnel-sim.sh
TARGET=$(sed -n 's/^ALLOWED_TARGET="\(.*\)"/\1/p' target.conf)
echo "$TARGET"
```

Analyst, on the dashboard (`https://<host>/`): log in, confirm the **Overview**
status strip is green and note the current alert count as the baseline.

---

## Act 1 — Reconnaissance (0:00)

**Operator:** run the port scan. This is the first thing an attacker does.

```bash
sudo ./port-scan.sh "$TARGET"
```

**Expected:** `NET-PORTSCAN-001` (MEDIUM) — ≥20 distinct destination ports from
one source inside 60 s. `live_ids_ips.py` also emits its own IDS alert
(`IDS-SIG-001`).

**Analyst:** open **Alerts**, filter by the attacker's `src_ip`. Call out:
severity, the `distinct_destination_ports` evidence, the source IP. Click
through to the alert detail and show the linked **raw events**.

> Point out the **threat banner**: a single MEDIUM scan is not enough to be
> alarming — the platform says so rather than crying wolf.

---

## Act 2 — Web exploitation (0:03)

**Operator:** DVWA must be at security level **low**. Send the four web
payloads:

```bash
./sqli-xss.sh "$TARGET" all          # sqli, xss, cmdi, traversal
./scanner-ua.sh "$TARGET"            # sqlmap / Nikto / nmap / gobuster UAs
```

**Expected:** `WEB-SQLI-001`, `WEB-XSS-001`, `WEB-CMD-001`, `WEB-LFI-001` (all
HIGH except XSS at MEDIUM) and `WEB-SCAN-001` (MEDIUM) from the scanner
User-Agents.

**Analyst:** open **Events** first — show the decoded `uri`/`body` on the raw
event (this is the nginx `soc` log format doing its job). Then **Alerts**: the
web payloads arrive as separate findings with the matching payload quoted as
evidence.

> This is the moment to note **deduplication**: repeat a payload and the *same*
> alert's `count` rises instead of a new alert appearing.

---

## Act 3 — SSH brute force, then success (0:06)

**Operator:**

```bash
./ssh-brute-force.sh "$TARGET" testuser passlist.txt
```

`passlist.txt` ends with the real password, so hydra stops on success.

**Expected:** `SSH-BF-001` (HIGH) on ≥10 failures in 5 minutes, then
`SSH-SUCCESS-001` (**CRITICAL**) — a successful login from an IP that already
has an open brute-force alert. This is the escalation moment.

**Analyst:** sort **Alerts** by severity — CRITICAL floats to the top. Open the
SSH-SUCCESS-001 alert. State the significance plainly: *the credential is now
considered compromised.*

---

## Act 4 — Correlation and incident (0:09)

**Analyst:** open **Chains**. The scan, web and SSH alerts from the same source
inside the correlation window have been grouped under one `chain_id`.

- Show the chain timeline (scan → web → SSH).
- Use the chain's **promote to incident** action.
- Open the new **incident**: it carries the severity, the affected host, the
  source IP and the member alerts.
- Add an investigation **note** (e.g. *"port scan → web exploit → SSH success
  from one source; treating as credential compromise"*).

> Talk track: individuals alerts are noise; the **chain** is the story; the
> **incident** is the unit of response.

---

## Act 5 — Containment: block the IP (0:12)

**Analyst:** from the incident (or the source alert), record a response action:

1. Action type **block IP**, target = the attacker's `src_ip`.
2. Confirm it. The backend runs `/usr/local/sbin/soc-block` via sudo.

**Expected:** the action's status becomes `executed`; the result line reads
`blocked <ip> for 3600s`.

**Operator/terminal (on the instance) — the proof it is real:**

```bash
sudo nft list set inet filter blocklist
ssh testuser@"$TARGET" true     # from Kali: connection now times out
```

**Analyst:** optionally demonstrate the guardrails:

- blocking a **non-IPv4** target → refused (HTTP 400);
- blocking an **allow-listed** IP → refused (HTTP 403);
- executing without `confirm: true` → refused.

> The block is a real nftables set entry, not a dashboard flag. This is the
> "response" half of detection-and-response.

---

## Act 6 — False-positive control (0:14)

**Operator:** switch the laptop to the **phone hotspot** (see
[`docs/testing/second-source-ip.md`](testing/second-source-ip.md)), note the new
public IP, and generate *benign* traffic:

```bash
curl -s https://ifconfig.me            # the second source IP
curl -sI "http://$TARGET/"             # one page load, a couple of 200s
```

**Expected:** the benign second source produces **no** alert (or only sub-
threshold noise). Contrast it with the attacker IP: same kind of HTTP GETs, but
one is normal use and one is exploitation — the difference is the payload shape
and volume, which is what the rules key on.

**Analyst:** in **Reports**, show the false-positive view: mark any stray benign
alert **FALSE POSITIVE** to show the triage state machine, then confirm the count.

---

## Wrap-up (0:15)

Recap the loop in one line: **collect → normalize → detect → correlate →
investigate → respond**, and that the response (**block IP**) is enforceable and
auditable.

Then clean up:

```bash
# On the instance: undo the block if you want a clean slate
sudo nft delete element inet filter blocklist { <attacker_ip> }
# Optionally resolve/close the incident for a tidy dashboard
```

Finish with the post-session box of
[`docs/testing/pre-session-checklist.md`](testing/pre-session-checklist.md):
record the two IPs, the alert IDs, and **stop the instance**.

---

## Contingencies

| If… | Do this |
|---|---|
| A rule doesn't fire live | Fall back to the **replay** suite (`detection/tests/replay_test.py`) and show the same alert in the dashboard from the seeded DB. Note it as a live-testing finding, not a demo failure. |
| DVWA blocks the script (session/CSRF) | Set DVWA to **low**, re-login in a browser on the Kali box; if still blocked, use `scanner-ua.sh` + the replay data for the web segment. |
| The attacker IP is blocked mid-run by the IDS's own auto-block | Clear it (`sudo nft delete element …`) or wait out the timeout; this is expected behaviour, not a bug. |
| Background internet scanning adds alerts | Filter by the operator's IP; call out the extra source as expected noise. |
| Hotspot IP is CGNAT/shared/changes | Record the actual IP at the time and note the trade-off from `second-source-ip.md`. |

## Rehearsals

Two timed rehearsals before the assessed run, logged here.

| # | Date (UTC) | Operator / Analyst | Full run to 0:15? | Issues found | Fix before live |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |

## Assets produced

| Asset | Where |
|---|---|
| Attack log (every script run) | `attack-sim/attack-log.txt` |
| Per-rule results | [`docs/testing/results.md`](testing/results.md) |
| Incident write-up | [`docs/reports/incident-reports.md`](../reports/incident-reports.md) |
| Slides | `docs/slides/` |
