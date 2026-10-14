# ec2-soc — EC2 host configuration snapshot

Point-in-time record of the host-level configuration of the Mini SOC EC2
instance. It was created by task **8.1** and replaces the original
`infrastructure/fw-01/` directory that the isolated multi-VM design used
(`fw-01` was removed in Phase 4 when the project moved to a single
internet-facing instance).

This directory is a **copy for review and reproducibility**, not the source
of truth that `deploy/install.sh` installs. That distinction matters:

- `deploy/` holds the repo-owned templates (`deploy/install.sh` renders and
  installs them).
- `infrastructure/ec2-soc/` records the full set of files the running host
  uses, including ones **not** managed by `install.sh` (sshd, DVWA, PHP-FPM,
   logrotate).

The exception is `nginx/mini-soc.conf`, which is the same template
`install.sh` renders — it is included here so all four web/host configs sit
together.

Every file carries an `Original path:` header naming where it belongs on the
host. Secrets are **placeholders**; the real values live only on the instance
(`/etc/mini-soc/.env`, `config.inc.php`). Never commit a real value here.

## Index

| File | Original path | Managed by |
|---|---|---|
| `nftables.conf` | `/etc/nftables.conf` | `deploy/install.sh` |
| `nginx/nginx.conf` | `/etc/nginx/nginx.conf` | OS package |
| `nginx/mini-soc.conf` | `/etc/nginx/sites-available/mini-soc.conf` | `deploy/install.sh` (renders `deploy/nginx/mini-soc.conf`) |
| `nginx/dvwa.conf` | `/etc/nginx/sites-available/dvwa.conf` | manual (see `docs/lab-setup.md`) |
| `sshd_config` | `/etc/ssh/sshd_config` | manual (OpenSSH default hardened) |
| `dvwa/config.inc.php` | `/var/www/dvwa/config/config.inc.php` | manual, secrets as placeholders |
| `php-fpm/www.conf` | `/etc/php/8.3/fpm/pool.d/www.conf` | OS package |
| `logrotate/NOTES.md` | `/etc/logrotate.d/` notes | manual |
| `security-group.json` | EC2 Security Group rules | AWS console |

## How these were produced

The box is reachable only with the AWS key pair, so this is an authored
snapshot rather than a live `scp` dump: every file matches what
`deploy/install.sh` plus the documented manual steps
(`docs/lab-setup.md`) install on a fresh Ubuntu 24.04 instance.

- `nftables.conf` is the operative file the IDS reads (`SOC_DROP:` /
  `SOC_ACCEPT:` / `SOC_OUT:`).
- Secrets (`dvwa/config.inc.php`, the SG's analyst CIDRs) are placeholders
  (`CHANGEME…`, `x.x.x.x/32`); the live values are never committed.

## Security Group screenshot

`security-group.json` is the machine-readable export. If you also want the
console screenshot, capture it and drop it next to this file
(`infrastructure/ec2-soc/security-group.png`); it is not committed by default
so the account/VPC IDs read from it can be scrubbed first.
