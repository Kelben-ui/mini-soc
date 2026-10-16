# Demo Script — Mini SOC (single EC2 deployment)

A 15-minute, live end-to-end demonstration of the Mini SOC: collect → detect →
correlate → triage → contain → report. It is also the script used for the two
timed rehearsals (Phase 9, task 9.4).

> **Original:** this adapts the original project §8 demo to the single EC2
> instance (one analyst, one attacker VM). The attack commands are the same as
> [`../attack-sim/`](../attack-sim/); the 13-rule expectations are in
> [`testing/live-runbook.md`](testing/live-runbook.md) and the results matrix in
> [`testing/results.md`](testing/results.md).

## Roles and setup

| Role | Who | Machine |
|---|---|---|
| **Presenter / analyst** | leads the run, drives the dashboard | laptop (analyst IP) |
| **Attacker** | runs the `attack-sim` scripts | Kali VM |
| **Narrator** (optional) | explains what the platform is doing | — |

**Before you start**

- [ ] `docs/testing/pre-session-checklist.md` completed (services active, DVWA
      security **low**, `target.conf` set, `passlist.txt` built, analyst IP
      allow-listed).
- [ ] Dashboard open and signed in as a lead/admin (needed for block/confirm and
      incident close). Overview page visible.
- [ ] Kali terminal open in `~/mini-soc/attack-sim` with `TARGET` exported.
- [ ] A second, benign source ready for the false-positive segment
      (`docs/testing/second-source-ip.md`) — e.g. a phone hotspot.
- [ ] `docs/reports/incident-reports.md` open in a second tab (the target output).
- [ ] Clock/timer visible; two rehearsals are timed.

> **Live-host note.** Rules 12 (outbound) and 13 (DNS) are **host-originated** and
> run *on the instance*, not from Kali. HTTP flood (#9) has no attack script —
> it is covered by replay and the synthetic `sample-data/` log.

---

## Running order (≈15 minutes)

### Act 1 — Posture (0:00–1:30)

**Presenter.** On the **SOC Overview**, introduce the platform: the threat-level
banner, open counts by severity, top sources and agent health. State that the
dashboard refreshes live (alerts within ~10 s, events every 8 s).

*Point to make:* "Everything we're about to see is detected from real log lines,
not mockups."

### Act 2 — Reconnaissance (1:30–3:00)

**Attacker (Kali):**
```bash
sudo ./port-scan.sh $TARGET        # → NET-PORTSCAN-001 (MEDIUM)
```

**Presenter.** Two ways to show it:

1. Open **Alerts** and find `NET-PORTSCAN-001`; note source IP, distinct-port
   count and that the linked raw events are the actual `SOC_DROP:` lines.
2. Click the alert and scroll to **Response playbook** — the **port scan**
   playbook (`port-scan.md`) is rendered for this rule, with its Trigger,
   Triage, Evidence, Containment, Recovery and Closure sections. This is the
   "what do I do now" view: a scan with no follow-on is often benign; the
   question the playbook asks is *what comes next*.

*Point to make:* "Each alert type brings its own playbook to the alert — the
analyst doesn't hunt for a procedure."

### Act 3 — Web exploitation (3:00–6:00)

**Attacker (Kali):**
```bash
./sqli-xss.sh $TARGET sqli          # → WEB-SQLI-001 (HIGH)
./sqli-xss.sh $TARGET xss           # → WEB-XSS-001 (MEDIUM)
./sqli-xss.sh $TARGET cmdi          # → WEB-CMD-001 (HIGH)
./sqli-xss.sh $TARGET traversal     # → WEB-LFI-001 (HIGH)
./scanner-ua.sh $TARGET             # → WEB-SCAN-001 (MEDIUM)
```

**Presenter.** Open one web alert (e.g. `WEB-SQLI-001`) and walk the playbook's
**Triage**: read the decoded payload, then decide from the HTTP status whether it
was *sent* or *succeeded*. Show the scanner UA and explain the tooling
fingerprint (`sqlmap`, `Nikto`) — this is automated, not a typo.

### Act 4 — Credential attacks (6:00–8:30)

**Attacker (Kali):**
```bash
./sqli-xss.sh $TARGET bruteforce     # → WEB-BF-001 (HIGH)
./ssh-brute-force.sh $TARGET testuser passlist.txt
                                     # → SSH-BF-001 (HIGH) then SSH-SUCCESS-001 (CRITICAL)
```

**Presenter.** Show the brute-force alert, then the **`SSH-SUCCESS-001`** alert
and make the point explicit: a failed brute force is an **attempt**; a success
after it is a **suspected compromise** and escalates to CRITICAL. Open that
alert's playbook (`ssh-success-after-bruteforce.md`) — the containment step is
block + `disable account` + `isolate host`.

### Act 5 — Host-originated activity (8:30–10:00)

**On the EC2 instance:**
```bash
./outbound-conn.sh 203.0.113.5 4444   # → NET-OUTBOUND-001 (MEDIUM)
./dns-tunnel-sim.sh                    # → DNS-ANOMALY-001 (LOW)
```

**Presenter.** Show that these are the *host* behaving oddly **after** compromise
— the "beaconing / exfiltration" signal. Use each playbook to decide victim vs.
sender (DNS) and whether the destination is legitimate egress to allow-list or
C2 to block.

### Act 6 — Correlation (10:00–11:00)

**Attacker (Kali):**
```bash
./recon-chain.sh $TARGET
```

**Presenter.** Open **Attack Chains**. All alerts from one source inside 30
minutes are grouped into **one chain**; open the chain detail to show the
kill-chain timeline. This is the pivot from "many tickets" to "one story".

### Act 7 — Triage and containment (11:00–13:00)

**Presenter.**

1. Move an alert `NEW → INVESTIGATING` and assign it to an analyst.
2. **Promote the chain to one incident** in a single click → `INC-…` (CRITICAL).
3. On the incident, record a **`block IP`** action for the attacker source and
   **confirm** it → the helper adds the address to the nftables `blocklist` set.
4. Show **Export evidence** on the alert/incident (events + SHA-256 + custody).
5. Return to a blocked alert and show **Block source IP** — it *records* a
   pending `block IP` action on the incident, which the analyst then confirms.

*Point to make:* "Nothing runs automatically. `block IP` is recorded first and
only executes after a human confirms it; allow-listed and non-IPv4 targets are
refused."

### Act 8 — Reporting and false-positive control (13:00–15:00)

**Presenter.**

- Add a note; walk the incident **timeline**; change status through
  `investigating → contained → resolved → closed`; produce the **report export**
  (HTML) — this is the artifact archived next to
  [`reports/incident-reports.md`](reports/incident-reports.md).
- **False positive:** have the benign second source load the DVWA page a few
  times. Volume stays **below every threshold** → no alert (or at most one
  sub-threshold scanner-UA hit) → mark it **FALSE POSITIVE** with a reason. Same
  request shape, different verdict, because the rules key on **payload and
  volume**, not on traffic merely existing.

### Close (15:00)

Recap the loop: **collect → detect → correlate → triage → contain → report**,
and that every alert carried its own playbook from first click to closure.

---

## Contingencies

| If… | Then… |
|---|---|
| A rule doesn't fire within ~30 s | Re-run the script; confirm the agent is heartbeating (Overview) and DVWA is at **low**. Check `docs/testing/live-runbook.md` §pre-flight. |
| Too many alerts to narrate | Filter the Alerts list by **Rule ID** or **Source IP** for the demo source; open the chain instead of individual alerts. |
| The block doesn't take | `nft list set inet filter blocklist` on the instance; the action must be **confirmed** (not just recorded). Allow-listed sources are intentionally refused. |
| Host-originated rules (#12/#13) can't run | Note they are on-host; fall back to the replay evidence in `docs/testing/results.md`. |
| Time is short | Skip Act 5; the chain in Act 6 still tells the multi-stage story. |
| A live demo alert is a false positive | Treat it as the Act 8 teaching moment rather than hiding it. |

## Rehearsal log

Run the script twice end-to-end on the live lab and record each pass. The two
timed rehearsals require the running EC2 instance and the Kali VM (Phase 9 task
9.4) and are **pending** until then.

| Date (UTC) | Operator | Rehearsal # | Duration | Issues | Pass/Fail |
|---|---|---|---|---|---|
| | | 1 | | | [PENDING] |
| | | 2 | | | [PENDING] |
