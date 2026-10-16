# Web login brute force (`WEB-BF-001`)

**Severity** HIGH · **Category** web · **MITRE** T1110 · **Source** Nginx access log

> A burst of login attempts against the web app from one source. Confirm whether
> any attempt succeeded.

## Trigger

≥20 `POST /login` requests from the same `src_ip` within 120 s. Threshold lives in
`rules/web_login_bruteforce.yaml`.

## Triage

1. Confirm the POST burst and the target path.
2. **Look for a successful login from the same IP after the burst** — check the
   Nginx `status` on later requests (a `200`/redirect vs `401`).
3. Correlate with `WEB-SCAN-001` and `NET-PORTSCAN-001` in the last 30 minutes.

## Evidence

- Export the login POST events; record the attempt count and whether a login
  succeeded.
- Note the targeted account(s) and the source IP.

## Containment

- Ongoing attempt → **Block IP** (3600 s).
- A successful credential use → treat as compromise: **Block IP** plus record
  **`disable account`** for the web account and reset it.

## Recovery

- Reset the targeted account's password.
- Confirm no content or configuration was changed by the account.
- Consider a lockout/rate-limit on the login endpoint.

## Closure

- Benign → **FALSE POSITIVE** with a reason.
- Real attempt, no success → **RESOLVED** with root cause and lessons learned.
- Success → full incident closure.

## Related

- **Rule definition:** `rules/web_login_bruteforce.yaml`
- **Reproduce:** `attack-sim/sqli-xss.sh <target> bruteforce`
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
