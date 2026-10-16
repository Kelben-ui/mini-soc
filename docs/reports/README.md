# Reports

Written output from the build and the lab: phase sign-offs and demo incident
reports.

## Phase sign-offs

One report per delivered phase, committed alongside that phase's work.

| Report | Covers |
|---|---|
| [`phase-1-signoff.md`](phase-1-signoff.md) | Repo skeleton, detection engine, rules 1–4 |
| [`phase-2-signoff.md`](phase-2-signoff.md) | Collector, event store, ingest API |
| [`phase-3-signoff.md`](phase-3-signoff.md) | Alerting, correlation, IDS/agent plumbing |
| [`phase-4-signoff.md`](phase-4-signoff.md) | Response actions, block-IP helper, remaining rules |
| [`phase-7-signoff.md`](phase-7-signoff.md) | Attack chains, incident tooling, dashboard pages |
| [`phase-7-signoff-cont.md`](phase-7-signoff-cont.md) | Phase 7 continuation (tasks 7.7–7.11) |
| [`phase-8-signoff.md`](phase-8-signoff.md) | EC2 host configs, architecture diagram, attack simulation |
| `phase-9-signoff.md` | Live EC2 testing, security review, playbooks, deliverables *(added with Phase 9)* |

Each report follows the same shape: verification commands and their results, a
task-by-task table, notable decisions, anything that could not be verified from
the build machine, and a sign-off row.

## Incident reports

Demo incident reports for the two Phase 9 narratives (a confirmed multi-stage
intrusion and a false-positive triage) live in
[`incident-reports.md`](incident-reports.md). They are worked examples for the
response playbooks in [`../../playbooks/`](../../playbooks/) — the umbrella
[`incident-response.md`](../../playbooks/incident-response.md) plus one playbook
per detection rule — not real customer data.

## Conventions

* Markdown, UTF-8, no byte-order mark.
* Reference the commit / baseline the report was written against.
* Distinguish what was **verified** from what was **authored** but needs the live
  host to confirm.
