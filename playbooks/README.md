# Playbooks

Incident-response playbooks for the Mini SOC. Each one maps the detection rules
the platform fires to the triage, evidence, containment, recovery and closure
steps an analyst follows.

| File | Covers |
|---|---|
| [`incident-response.md`](incident-response.md) | **The single playbook.** All 13 rules, grouped into scenarios (recon, SSH brute force, web attacks, web login brute force, HTTP flood, DNS anomaly, outbound, generic IDS signature). |

## One copy, one source of truth

`incident-response.md` is the **only** authored playbook. The dashboard serves a
build-time copy of it: `frontend/scripts/sync-playbooks.mjs` copies
`playbooks/*.md` into `frontend/public/playbooks/`, and that generated directory
is git-ignored. `npm run dev` and `npm run build` run the sync automatically
(`predev` / `prebuild`).

```
playbooks/incident-response.md          <- edit this
        │  sync-playbooks.mjs
        ▼
frontend/public/playbooks/             <- generated, git-ignored
        │  vite build
        ▼
frontend/dist/playbooks/incident-response.md   <- served at /playbooks/
```

The alert detail view maps every rule ID to this file via
`frontend/src/playbookMap.js`.

## Conventions

- **Containment is the confirmed `block IP` action** — the only response action
  the platform executes (it runs `/usr/local/sbin/soc-block`, adding the address
  to the nftables `blocklist` set with a timeout). `disable account` and
  `isolate host` are recorded on the timeline but carried out manually.
- Thresholds and severities in the playbook mirror the YAML in
  [`../rules/`](../rules/). If a rule changes, update the playbook too.
- Alert states: `NEW → INVESTIGATING → CONTAINED → RESOLVED` (or
  `FALSE POSITIVE` from `NEW`/`INVESTIGATING`, reason required).
- Incident states: `open → investigating → contained → resolved → closed`
  (closing needs an analyst/lead role).
