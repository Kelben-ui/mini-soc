# Second source IP for the false-positive demo

**Decision (task 8.4): use a phone hotspot as the second attacker IP.**

## What this is for

The detection rules key on `src_ip`, so a *correct* low-false-positive
result is one where normal approved activity from a second IP does **not**
raise alerts. The original physical-lab design had a second VM for this.
On a single internet-facing EC2 instance the "second IP" has to be a real
second source we control.

The demo is: from the **primary** analyst/lab IP, run a script that
legitimately should be seen (or should be allow-listed) — e.g. the DVWA
login or a short port touch — and confirm that from the **second** IP the
same benign traffic produces **far fewer or no** alerts, or that the
allow-list suppresses it as designed.

## Options considered

| Option | Pro | Con | Chosen |
|---|---|---|---|
| **Phone hotspot** | Genuinely different public IP; no extra cost; no server to build; disconnect/reconnect quickly | IP may be CGNAT and shared; mobile uplink latency can be high | **Yes** |
| Commercial VPN | Instant new IP; scriptable | Can be noisy/rate-limited; some VPNs are already on block-lists; the IP is shared and can change mid-session | No |
| Second small EC2 | Full control, stable IP, in the same account | Extra instance cost + another thing to keep secure/stopped; the second IP is *in the same account*, which muddies the "outside vs approved" story | No |

## Why the hotspot

- It gives a genuinely different public IP with **no extra infrastructure**
  and no cost beyond the phone plan already in use.
- It is trivially separable in the dashboard: the two sources are obvious
  and distinguishable.
- It keeps the "second, benign source" story honest — the hotspot is not a
  second box in the AWS account that a viewer might think is part of the
  deployment.

## Trade-offs to record in the demo

- A phone hotspot IP is **NATed and shared**; if the carrier rotates it
  mid-demo, re-check the IP and re-map it in the notes.
- If the hotspot's IP happens to be flagged as known-bad, treat that as a
  finding, not a script failure.

## How to run the demo

1. Complete `docs/testing/pre-session-checklist.md` from the primary IP.
2. Connect the laptop to the phone hotspot (or a second device on it),
      note the public IP (`curl -s https://ifconfig.me`).
2. From the second IP, perform a short, benign action that the primary
   session would flag if it came from an unapproved source — for example
   a single DVWA login page load plus one failed login, or a very short
   port touch to 80.
3. On the dashboard, confirm the second IP's activity either does not
   alert or is explained (allow-listed / below threshold) — record the
   result.
- Then restore the primary IP and continue.

Record the two IPs and the outcome in the session log at the bottom of
`docs/testing/pre-session-checklist.md`.

## Where this is referenced

- `docs/architecture.md` §4 (single EC2 instance, attacker from the
  internet).
- `attack-sim/README.md` known items.
