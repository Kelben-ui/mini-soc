# Login success after brute force (`SSH-SUCCESS-001`)

**Severity** CRITICAL · **Category** authentication · **MITRE** T1078 · **Source** `auth.log`

> A successful SSH login from a source that has an **open** brute-force alert.
> First failed guesses, then an `Accepted` — this is a **suspected compromise**,
> not an attempt. Escalate now.

## Trigger

A successful `ssh_login` event whose source is correlated to an open brute-force
alert (`SSH-BF-001`). Logic lives in `rules/ssh_success_after_bruteforce.yaml`.

This is the single most important alert in the platform: the difference between a
failed brute force and this one is the difference between "attempted" and
"compromised".

## Triage

1. **Assume the account is compromised.** Identify the username that logged in and
   the source IP.
2. Confirm the preceding brute-force alert and its count; the success should be in
   the same alert/chain window.
3. Correlate: the same source may also have produced `NET-PORTSCAN-001` and web
   alerts — this is a multi-stage intrusion, promote the **chain** to one incident.
4. Establish the blast radius: what can that account reach, and has the host done
   anything new since the login (`NET-OUTBOUND-001`, `DNS-ANOMALY-001`)?

## Evidence

- Export the `auth.log` events for **both** the failed burst and the successful
  login; keep them under the same incident.
- Record: `src_ip`, username, target host, timestamp of the `Accepted`, and the
  commands/sessions associated with the account if available.

## Containment

- **Block IP** for the source immediately.
- Record **`disable account`** for the compromised user and reset its password and
  `authorized_keys` out-of-band.
- Treat `soc-01` as potentially compromised: record **`isolate host`** and involve
  a lead.

## Recovery

- Rotate every credential the account could reach; review `authorized_keys`,
  `sudoers`, cron, and any new users.
- If the host is confirmed compromised, rebuild from the clean-baseline AMI rather
  than cleaning in place.
- Confirm no lingering sessions or scheduled tasks after the password reset.

## Closure

- **Never close as FALSE POSITIVE without proof** the success was expected
  (e.g. a documented, approved test with the correct credentials).
- Otherwise: root cause, credential reset, rebuild decision, and lessons learned —
  closed by a lead.

## Related

- **Rule definition:** `rules/ssh_success_after_bruteforce.yaml`
- **Reproduce:** `attack-sim/ssh-brute-force.sh <target> testuser passlist.txt`
  (the passlist ends with the real password)
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
