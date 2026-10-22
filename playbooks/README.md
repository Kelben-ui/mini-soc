# Playbooks

Incident-response playbooks for the Mini SOC. Each one maps a detection rule to
the triage, evidence, investigation, containment, recovery and closure steps an
analyst follows.

Every rule has its **own standalone playbook**. The alert detail page loads the
playbook for the rule that fired, so an analyst opening an alert sees exactly the
procedure for that alert type — not a wall of every scenario. The umbrella
[`incident-response.md`](incident-response.md) holds the platform model, the
universal steps, the shared containment / closure / reporting rules, and the
index.

## Per-alert playbooks

| Alert (rule) | Severity | Playbook |
|---|---|---|
| SQL injection (`WEB-SQLI-001`) | HIGH | [`web-sqli.md`](web-sqli.md) |
| Cross-site scripting (`WEB-XSS-001`) | MEDIUM | [`web-xss.md`](web-xss.md) |
| Command injection (`WEB-CMD-001`) | HIGH | [`web-command-injection.md`](web-command-injection.md) |
| Directory traversal / LFI (`WEB-LFI-001`) | HIGH | [`web-traversal-lfi.md`](web-traversal-lfi.md) |
| Scanner user-agent (`WEB-SCAN-001`) | MEDIUM | [`web-scanner-user-agent.md`](web-scanner-user-agent.md) |
| Web login brute force (`WEB-BF-001`) | HIGH | [`web-login-bruteforce.md`](web-login-bruteforce.md) |
| HTTP flood (`WEB-FLOOD-001`) | MEDIUM | [`http-flood.md`](http-flood.md) |
| SSH brute force (`SSH-BF-001`) | HIGH | [`ssh-brute-force.md`](ssh-brute-force.md) |
| Login success after brute force (`SSH-SUCCESS-001`) | CRITICAL | [`ssh-success-after-bruteforce.md`](ssh-success-after-bruteforce.md) |
| Port scan (`NET-PORTSCAN-001`) | MEDIUM | [`port-scan.md`](port-scan.md) |
| Generic IDS signature (`IDS-SIG-001`) | HIGH | [`ids-signature.md`](ids-signature.md) |
| Unusual DNS activity (`DNS-ANOMALY-001`) | LOW | [`unusual-dns.md`](unusual-dns.md) |
| Unusual outbound connection (`NET-OUTBOUND-001`) | MEDIUM | [`unusual-outbound.md`](unusual-outbound.md) |
| **Umbrella** (platform model, universal steps, index) | — | [`incident-response.md`](incident-response.md) |

`frontend/src/playbookMap.js` maps each rule ID to its file; any rule without an
entry falls back to the umbrella.

## One copy, one source of truth

Each playbook is authored **once** under `playbooks/`. The dashboard serves a
build-time copy: `frontend/scripts/sync-playbooks.mjs` copies every `playbooks/*.md`
(except this README) into `frontend/public/playbooks/`, and that generated
directory is git-ignored. `npm run dev` and `npm run build` run the sync
automatically (`predev` / `prebuild`).

```
playbooks/*.md                          <- edit these (one per rule + the umbrella)
        │  sync-playbooks.mjs
        ▼
frontend/public/playbooks/             <- generated, git-ignored
        │  vite build
        ▼
frontend/dist/playbooks/*.md           <- served at /playbooks/
        │  AlertDetail.jsx  (rule_id -> playbookMap.js)
        ▼
Rendered on the alert detail page
```

## Conventions

- **Every playbook uses the same six sections**, in the same order, each owned
  by a named role and written as direct commands: `1. Triage — Analyst`,
  `2. Evidence Collection — Analyst`, `3. Investigation — Analyst`,
  `4. Containment — Lead / Admin`, `5. Remediation and Recovery — Admin /
  <owner>`, `6. Closure — Admin`. A `**Important:**` line closes each one with
  what the alert does and does not prove, followed by a short `Related` footer
  (rule YAML, reproduce command, umbrella link).
- **Containment is the confirmed `block IP` action** — the only response action
  the platform executes (it runs `/usr/local/sbin/soc-block`, adding the address
  to the nftables `blocklist` set with a timeout). `disable account` and
  `isolate host` are recorded on the timeline but carried out manually.
- **No action is automatic.** `block IP` is recorded first and only runs after a
  human confirms it; allow-listed and non-IPv4 targets are refused.
- Thresholds and severities in each playbook mirror the YAML in
  [`../rules/`](../rules/). If a rule changes, update its playbook too.
- Alert states: `NEW → INVESTIGATING → CONTAINED → RESOLVED` (or
  `FALSE POSITIVE` from `NEW`/`INVESTIGATING`, reason required).
- Incident states: `open → investigating → contained → resolved → closed`
  (only the admin closes an incident; the analyst or lead prepares the closure
  record).

## Adding a rule

1. Add the rule YAML under [`../rules/`](../rules/).
2. Add a playbook here (copy an existing one as a template) and list it in the
   tables above and in [`incident-response.md`](incident-response.md) §4.
3. Point `frontend/src/playbookMap.js` at the new file. The
   `playbookMap.test.js` coverage test fails until every rule has a playbook.
