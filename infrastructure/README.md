# Infrastructure (`infrastructure/`)

Host configuration for the deployed environment. This tree is a **reviewable
snapshot / reference**, not an installer — the source of truth for provisioning
is [`../deploy/`](../deploy/) (`install.sh` renders the live files).

## `ec2-soc/`

The single EC2 SOC instance (`soc-01`): nftables ruleset, nginx sites, sshd and
PHP-FPM configuration, the DVWA target's config, log-rotation notes and the AWS
Security Group export. Each file carries an `Original path:` header showing
where it lives on the host.

See [`ec2-soc/README.md`](ec2-soc/README.md) for the full file index.

## Relationship to `deploy/`

| Concern | `deploy/` (installer) | `infrastructure/` (snapshot) |
|---|---|---|
| Purpose | Provision and update the host | Document what the host runs |
| `nftables` | `deploy/nftables/mini-soc.conf` (templated) | `infrastructure/ec2-soc/nftables.conf` |
| nginx | `deploy/nginx/mini-soc.conf` (dashboard on :443) | dashboard site + DVWA site + main `nginx.conf` |
| services | `deploy/systemd/*.service` | — |
| sshd / PHP / DVWA | not automated (manual steps in `../docs/lab-setup.md`) | captured here |

The earlier multi-VM layout (`fw-01`, `web-01`, `srv-01`, `atk-01`) was removed
when the project moved to one EC2 instance; `infrastructure/` now holds only
`ec2-soc/`.

## Building the environment from scratch

Follow [`../docs/lab-setup.md`](../docs/lab-setup.md): Security Group, Elastic
IP, `deploy/install.sh`, then the manual DVWA/MariaDB/PHP-FPM and `sshd` steps.
The result can be frozen as a clean-baseline AMI for repeatable demos.
