# Documentation (`docs/`)

All project documentation. Start with the root [`../README.md`](../README.md)
for the one-command install, then use the table below.

## Design & reference

| Document | Audience | Contents |
|---|---|---|
| [`architecture.md`](architecture.md) | All | System architecture, component lifecycle, deviations from the reference spec, the architecture diagram. |
| [`contracts.md`](contracts.md) | Developers | The data contracts: event schema, alert/incident/action models, API shapes, status machines. |
| [`rules.md`](rules.md) | All | Human-readable specification of the detection rules. |
| [`lab-setup.md`](lab-setup.md) | Ops / demo | Building the EC2 host from scratch (Security Group, install, DVWA, AMI snapshot). |
| [`demo-script.md`](demo-script.md) | Presenters | The timed end-to-end demo runbook (roles, acts, contingencies, rehearsal log). |
| [`user-guide.md`](user-guide.md) | Analysts | How to use the dashboard: triage, incidents, actions, reporting. |

## Testing

| Document | Contents |
|---|---|
| [`testing/test-plan.md`](testing/test-plan.md) | The test plan and the **rule → trigger** matrix. |
| [`testing/second-source-ip.md`](testing/second-source-ip.md) | How the false-positive demo uses a second (allow-listed) source. |
| [`testing/pre-session-checklist.md`](testing/pre-session-checklist.md) | Pre-demo / pre-test checklist and session log. |
| `testing/results.md` | Live attack-simulation results vs expected (Phase 9). |
| `testing/security-test.md` | Platform security testing: the 7 checks and findings (Phase 9). |
| [`testing/screenshots/`](testing/screenshots/) | Tooling that seeds a demo DB and captures the user-guide screenshots (Playwright). |

## Reports

| Document | Contents |
|---|---|
| [`reports/`](reports/) | Phase sign-off reports (`phase-N-signoff.md`) and incident reports. See [`reports/README.md`](reports/README.md). |
| [`reports/incident-reports.md`](reports/incident-reports.md) | Two worked incident reports (confirmed intrusion + false positive). |

## Slides

| Asset | Contents |
|---|---|
| [`slides/mini-soc-overview.pptx`](slides/mini-soc-overview.pptx) | 16-slide project overview (problem, architecture, rules, demo, response, quality). |
| [`slides/build_slides.py`](slides/build_slides.py) | Reproducible generator (python-pptx) for the deck. |

## Images

| Asset | Contents |
|---|---|
| [`images/architecture.png`](images/architecture.png) | Rendered architecture diagram (embedded in the README/architecture doc). |
| [`images/architecture.drawio`](images/architecture.drawio) | Editable diagram source. |
| [`images/render_architecture.py`](images/render_architecture.py) | Self-contained stdlib renderer (drawio → PNG), no external tools needed. |
| [`images/screenshots/`](images/screenshots/) | Dashboard screenshots used by the user guide (captured by `testing/screenshots/`). |

## Conventions

- Phase sign-off reports live in `reports/` and are committed with the phase.
- Screenshots used by the user guide live in `images/` and are captured with
  Playwright (`docs/testing/screenshots/` tooling).
