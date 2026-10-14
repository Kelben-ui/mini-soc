# Phase 8 — EC2 host configs & attack simulation — Sign-off Report

> **Status:** Implemented / verified / signed off
> **Date:** 2026-10-14
> **Baseline:** branch `main`, previous head `62aff91` (Phase 7 continuation report).
> This report accompanies the single Phase 8 commit.
> **Scope:** Phase 8 tasks 8.1–8.6 — the EC2 host-config snapshot, the rewritten
> lab-setup guide, the architecture diagram (draw.io + PNG), the second-source-IP
> decision for the false-positive demo, the attack-sim corrections and the
> pre-session checklist.
> **Method:** authored configs (the live instance is reached only with the AWS
> key pair), plus repeatable shell/script checks and the same pytest / replay /
> frontend suites used by the earlier phases.

---

## 1. Verification commands and results

| Check | Command | Result |
|---|---|---|
| Shell syntax (new + edited attack-sim/deploy scripts) | `bash -n <script>` for all 11 scripts | **all OK** |
| Python components | `pytest ids backend collector agents -q` | **116 passed, 1 skipped** |
| Detection replay (13 rules vs SQLite) | `python detection/tests/replay_test.py` | **PASSED** — 13/13 rules, 341 alert↔event links |
| Frontend unit/component tests | `npm test` (`vitest run`) | **18 passed** (5 files) |
| Frontend production build | `npm run build` | **ok** |
| Frontend lint | `npm run lint` (`oxlint`) | **0 errors** (pre-existing warnings only) |
| Diagram PNG is a valid, complete PNG | IHDR/IDAT decode check | **1500×1040, raw IDAT == H·(1+W·3)** |

The one skipped test is the POSIX-only log-agent rotation test carried over from
Phase 3/4; unrelated to this change.

## 2. Task-by-task

| Task | Result | Evidence |
|---|---|---|
| 8.1 Host-config snapshot | Pass | New `infrastructure/ec2-soc/` replaces the deleted `fw-01` box layout: `nftables.conf` (22/80/443 accept + `SOC_ACCEPT:`/`SOC_DROP:`/`SOC_OUT:` logging + `@blocklist`), `nginx/nginx.conf` (frozen `soc` log format), `nginx/mini-soc.conf` (dashboard :443) **and** `nginx/dvwa.conf` (web target :80), `sshd_config`, `dvwa/config.inc.php` (placeholder secret), `php-fpm/www.conf`, `logrotate/NOTES.md`, `security-group.json`, and an index `README.md`. Every file carries an `Original path:` header. |
| 8.2 Lab-setup rewrite | Pass | `docs/lab-setup.md` rewritten as a from-scratch Ubuntu 24.04 / `t3.small` / 30 GiB `gp3` build guide: Elastic IP, Security Group table, `deploy/install.sh`, DVWA + MariaDB + PHP-FPM, `testuser`, clean-baseline AMI, stop-when-idle, troubleshooting. |
| 8.3 Architecture diagram | Pass | Hand-authored `docs/images/architecture.drawio` plus a self-contained stdlib renderer `docs/images/render_architecture.py` that emits `docs/images/architecture.png`. Embedded in `README.md` and `docs/architecture.md` §1. No draw.io/Graphviz/Pillow needed. |
| 8.4 Second attacker IP | Pass | `docs/testing/second-source-ip.md` records the decision (**phone hotspot**) with the options table and the false-positive demo method; `docs/architecture.md` §4 and `attack-sim/README.md` cross-link it. |
| 8.5 Attack-sim fixes | Pass | Added `attack-sim/target.conf.example` (gitignored `target.conf` + `attack-log.txt`); added `attack-sim/scanner-ua.sh` (the missing trigger for WEB-SCAN-001); fixed `recon-chain.sh` / docs / script usage to the real names `sqli-xss.sh` and `ssh-brute-force.sh`; documented that the HTTP-flood rule is replay-only; `docs/testing/test-plan.md` now shows **every** rule has a trigger path. |
| 8.6 Pre-session checklist | Pass | `docs/testing/pre-session-checklist.md`: confirm the instance/SG, analyst IP allow-list, service health, session goal, post-session record, and a session-log table. |

## 3. Notes and decisions

1. **Snapshot vs installer.** `infrastructure/ec2-soc/` is a reviewable record of
   the running host, not an install source; `deploy/` stays the source of truth
   for `install.sh`. `nginx/mini-soc.conf` is the same template `install.sh`
   renders, included so all four web/host configs sit together.
2. **Authored, not scraped.** The box is reachable only with the AWS key pair, so
   the configs were authored to match `deploy/install.sh` plus the documented
   manual steps. Secrets are placeholders (`CHANGEME…`, `<ANALYST_CIDR>/32`).
3. **Host firewall logs accepts too.** The 8.1 `nftables.conf` logs accepted
   management/attack/dashboard ports as `SOC_ACCEPT:` in addition to
   `SOC_DROP:`/`SOC_OUT:`, per the task brief.
4. **Port split.** DVWA is the world-open :80 `default_server`; the SOC dashboard
   is :443 and is analyst-only via the Security Group. nginx defines the `soc`
   log format once (in `nginx.conf`).
5. **Diagram tooling.** No draw.io CLI, Graphviz, ImageMagick, Inkscape or
   Pillow is available, so the PNG is produced by a small built-in 5×7 bitmap-font
   renderer using only `zlib`/`struct`.
6. **Flood is replay-only, by design.** Sending >300 requests/min from a laptop at
   an internet-facing EC2 instance resembles the DoS traffic AWS restricts, so
   WEB-FLOOD-001 has no live script; the replay suite and `sample-data/` cover it.

## 4. Not verifiable from this machine

- The live EC2 instance itself: the authored configs match the documented install,
  but a real `scp`/diff against the running host needs the key pair.
- Running `port-scan.sh` / `ssh-brute-force.sh` / `sqli-xss.sh` / `scanner-ua.sh`
  (they run from the Kali attacker VM and need `nmap`/`hydra`).
- Applying the Security Group export in AWS and capturing the console screenshot.

These are executed as part of Phase 9 (live testing and deployment rehearsal).

## 5. Sign-off

All Phase 8 tasks 8.1–8.6 are implemented, and everything that runs off-box is
green: 11/11 shell scripts pass `bash -n`, the combined Python suite is 116 passed
(1 skipped), the 13-rule replay passes, the frontend build/test/lint are clean,
and the generated diagram PNG decodes fully.

| Reviewer | Role | Sign-off | Date |
|---|---|---|---|
| Team | EC2 host configs & attack simulation | Approved | 2026-10-14 |
