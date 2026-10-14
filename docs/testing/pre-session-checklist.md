# Pre-session checklist

Run through this **before** every attack-simulation / rehearsal session
(task 8.6). It takes a minute and prevents the two mistakes that waste a
session: attacking the wrong host (the AWS account may already run other
EC2 instances with your rules) and mis-reading the Security Group.

This complements `docs/testing/test-plan.md`, which is the rule-by-rule
test matrix. Fill in one row per session at the bottom.

## 1. Confirm the target is your own instance

- [ ] You have the **public IP / Elastic IP** of the Mini SOC EC2 instance
      (`mini-soc`) in the AWS account, from the instance details page — not a
      remembered value, since a restarted instance without an Elastic IP
      changes its IP.
- [ ] That IP is the only thing you will point the scripts at, and it is set
      in `attack-sim/target.conf` as `ALLOWED_TARGET`.
- [ ] You can identify which AWS resource that IP belongs to (console shows
      instance `mini-soc`).
- [ ] It is your own AWS account / your own project instance. If in doubt,
      **stop** — do not scan.

> The attack-sim scripts refuse to run against anything that is not exactly
> `ALLOWED_TARGET` in `target.conf`. Treat that as a safety belt, not a
> substitute for checking.

## 2. Confirm the Security Group

- [ ] The instance's Security Group is the group expected
      (`infrastructure/ec2-soc/security-group.json`).
- [ ] Inbound has **only**:
      - tcp 22 from `0.0.0.0/0` (SSH attack/analysis),
      - tcp 80 from `0.0.0.0/0` (DVWA target),
      - tcp 443 from the **analyst's current IP** (dashboard/API).
- [ ] The analyst's current IP still matches the 443 rule — home/ISP IPs
      can change, and a stale rule locks you out of the dashboard while
      you're already in a session.
- [ ] No other ports (no Postgres 5432, no collector 9000, no 8000) are
      open.
- [ ] Outbound is the expected state for the session.

## 3. Confirm the host + services

- [ ] `ssh` to the instance works with the project key.
- [ ] `systemctl --no-pager --failed` is clean and
      `soc-backend soc-collector soc-detection soc-agent mini-soc-ids`
      are `active`.
- [ ] `curl -sk https://localhost/api/stats` (or the dashboard) answers.
- [ ] DVWA is reachable on port 80 and set to security level **low**.
- [ ] The IDS is writing: `sudo tail -n1 /var/log/mini_soc_ids.json`
      works and the file is fresh after a test event.

## 3b. Analyst IP allow-list

- [ ] The analyst machine's public IP is in
      `/etc/mini-soc/allowlist.txt` (rendered from
      `ids.yaml`'s `allow_list.analyst_ips`) so the dashboard's own
      operator doesn't raise noisy alerts while the box is world-reachable.
- [ ] That allow-list matches the address you actually appear as
      (`curl -s https://ifconfig.me`), not a remembered one.

## 3.5 Session goal

- [ ] The rule(s) you intend to exercise are named (matrix row in
      `docs/testing/test-plan.md`).
- [ ] If this is the false-positive demo, the **second source** is planned
      and matches `docs/testing/second-source-ip.md`.

## 4. After the session

- [ ] `attack-sim/attack-log.txt` has the run entries (kept as evidence).
- [ ] The dashboard/API shows the expected alert(s); record actuals in
      `docs/testing/test-plan.md`.
- [ ] Any unexpected alert from an unfamiliar IP was noted separately
      (background internet scanning), not mixed into your result.
- [ ] **Stop the instance** when done for the day (cost + exposure), per
      `docs/lab-setup.md`.

---

## Session log

One row per session. The script itself writes the per-run detail to
`attack-sim/attack-log.txt`; this is the human-facing record.

| Date (UTC) | Operator | Target IP | SG reviewed | Analyst IP allow-listed | Goal / rules | Outcome |
|---|---|---|---|---|---|---|
| | | | | | | |
