# SSH brute force (`SSH-BF-001`)

**Severity** HIGH · **Category** authentication · **MITRE** T1110 · **Source** `auth.log`

> Repeated failed SSH logins from one source to one host. This is an **attempt**,
> not yet a compromise — confirm that no login succeeded before you close it.

## Trigger

≥10 failed `ssh_login` events from the same `src_ip` to the same `dst_ip` within
300 s. The threshold lives in `rules/ssh_brute_force.yaml`.

The custom IDS may also raise its own SSH signature (`9000002`), which arrives as
`IDS-SIG-001` — the **same activity** seen from a second source. Investigate them
together and do not double-count a single attack as two.

## Triage

1. Confirm the failed-login burst and the targeted username(s). One account
   targeted = brute force; many accounts = password spraying.
2. **Check for a success from the same source.** If `SSH-SUCCESS-001` fired,
   treat this as a *suspected compromise* and escalate immediately.
3. Correlate over the last 30 minutes: a `NET-PORTSCAN-001` from the same IP is
   the classic recon → brute-force chain. Open the **Chains** view and treat a
   correlated set as one incident.
4. Check the source against the allow-list (`rules/allowlist.yaml`). An approved
   test IP is a false positive.

## Evidence

- On the alert, use **Export evidence** to attach the linked `auth.log` events to
  the incident (stored with a SHA-256 hash and chain of custody).
- Record: `src_ip`, target host, targeted username(s), attempt count, window, and
  whether a success occurred.

## Containment

- Attempts only, traffic ongoing → **Block IP** for the source (3600 s) once the
  threshold is confirmed.
- `block IP` is the only executable action: it is first *recorded* on the
  incident, then you **confirm** it, and only then does the backend run
  `soc-block`.
- If a success occurred, also record **`disable account`** for the compromised
  username and reset its credentials and `authorized_keys` out-of-band.

## Recovery

- Confirm normal SSH from approved sources still works after the block.
- Confirm no new `authorized_keys`, users, or cron entries on the host.
- Longer term: key-only SSH (`PasswordAuthentication no`) and host rate-limiting
  (`MaxStartups`).

## Closure

- Benign (e.g. an approved test IP) → **FALSE POSITIVE** with a reason.
- Real attempt, no success → alert **RESOLVED**; incident `resolved` → `closed`.
- Success → full incident closure with root cause, credential reset, and lessons
  learned.

## Related

- **Rule definition:** `rules/ssh_brute_force.yaml`
- **Reproduce:** `attack-sim/ssh-brute-force.sh <target> testuser passlist.txt`
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
