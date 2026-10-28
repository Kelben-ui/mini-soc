# Infrastructure (`infrastructure/`)

Host configuration snapshots and references for the deployed environment. This
tree is a **reviewable snapshot / reference**, not an installer — the source of
truth for provisioning is [`../deploy/`](../deploy/) (`install.sh` renders the
live files).

## `host-config/` (or local snapshots)

Host-level configuration snapshots (nftables, nginx, sshd, PHP-FPM, etc.) may be
stored here for review. Each file should carry an `Original path:` header
showing where it lives on the host.

## Relationship to `deploy/`

| Concern | `deploy/` (installer) | `infrastructure/` (snapshot) |
|---|---|---|
| Purpose | Provision and update the host | Document what the host runs |
| `nftables` | `deploy/nftables/mini-soc.conf` (templated) | snapshot files as applicable |
| nginx | `deploy/nginx/mini-soc.conf` (dashboard on :443) | snapshot files as applicable |
| services | `deploy/systemd/*.service` | — |
| sshd / PHP / DVWA | manual steps in `../docs/lab-setup.md` | captured in snapshots if present |

## Building the environment from scratch

Follow [`../docs/lab-setup.md`](../docs/lab-setup.md): set up the host, run
`deploy/install.sh`, then apply manual DVWA/MariaDB/PHP-FPM and `sshd` steps as
documented.
