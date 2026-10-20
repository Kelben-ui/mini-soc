# Local (WSL2) lab harness

Repeatable tooling for running the Mini SOC stack inside **WSL2 Ubuntu-24.04**
— the same OS as the lab AMI — when the EC2 instance is unavailable. It
reproduces the full path (firewall → nginx → DVWA → agent → collector →
detection → API) without leaving the machine.

The first run's findings are written up in
[`../local-wsl-run.md`](../local-wsl-run.md).

## Files

| File | Purpose |
|---|---|
| `setup-attacker.sh` | Create the `atk` network namespace + veth pair (attacker `10.99.0.2` → host `10.99.0.1`) |
| `run-tests.sh` | Bounded smoke tests for the firewall, nginx and web-detection path |
| `verify.sh` | API-level view of event/alert counts and recent rows |

## Why a network namespace?

The lab ruleset accepts all loopback traffic:

```
iif "lo" accept
```

So anything sent to `127.0.0.1` bypasses nftables and cannot exercise the
firewall's drop / port-scan path. The `atk` namespace gives the host a
real-interface peer with an external-looking source IP, which is what
`Kali → EC2` looks like in the real lab.

> The namespace does **not** survive a WSL restart. Re-run `setup-attacker.sh`
> after every reboot.

## Quick start

```bash
# 0. one-time: copy the repo into WSL's ext4 filesystem (not /mnt/c) and
#    provision the stack
sudo MINI_SOC_APP_DIR=/root/mini-soc DOMAIN=localhost bash /root/mini-soc/deploy/install.sh

# 1. attacker namespace
sudo bash setup-attacker.sh

# 2. smoke tests (firewall + nginx + web detection)
sudo APP_DIR=/root/mini-soc bash run-tests.sh all

# 3. inspect the result through the API
bash verify.sh baseline     # before an attack
bash verify.sh delta        # after one: counts + newest alerts
bash verify.sh query nginx_access
```

## Requirements

- WSL2 with systemd enabled (`/etc/wsl.conf` → `[boot] systemd=true`).
- The stack provisioned by `deploy/install.sh` (nginx, nftables, PostgreSQL,
  MariaDB/PHP-FPM, DVWA, the six SOC services).
- DVWA initialised once via `/dvwa/setup.php` → *Create / Reset Database*
  (creates `admin` / `password`).
- `run-tests.sh` and `setup-attacker.sh` need root; `verify.sh` does not.
- If `verify.sh` cannot log in, set `SOC_USER` / `SOC_PASS` to an admin
  account. The local lab resets the dashboard admin password to a throwaway
  value during setup; export it rather than editing this script.

## Line endings

The scripts in this directory are checked in with LF endings (see the root
`.gitattributes`). If you copied the repo to Windows first, strip CRs before
running them inside WSL:

```bash
sed -i 's/\r$//' *.sh
```
