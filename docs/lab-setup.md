# Lab setup — rebuilding the Mini SOC EC2 instance

This is the build-from-scratch guide for the lab. It is written so that
someone with the project's AWS credentials can stand the instance up
without any other context (task 8.2). The **clean baseline** is an AMI you
snapshot at the end, so this whole page only has to be done once.

> Host-config copies live in `infrastructure/ec2-soc/` for review; the
> authoritative installer is `deploy/install.sh`. Where a step says to edit
> a file, `infrastructure/ec2-soc/` has the same file with the
> expected settings and an `Original path:` header.

---

## 0. What you need

| Item | Value |
|---|---|
| AWS account | the project account (coordinate so you don't fork the instance) |
| Region | any with the instance type; the current lab is a single region |
| Key pair | the project `*.pem` (never committed — see `.gitignore`) |
| Repo | `https://github.com/Kelben-ui/mini-soc` |
| Local Kali VM (attacker) | separate machine/laptop, not in AWS |

---

## 1. Launch the instance

In **EC2 → Launch instance**:

| Setting | Value |
|---|---|
| Name | `mini-soc` |
| AMI | **Ubuntu Server 24.04 LTS (HVM), SSD volume type** (amd64) |
| Instance type | **`t3.small`** (2 vCPU, 2 GiB) — the floor for nginx + PHP-FPM + MariaDB + DVWA + Postgres + the SOC services |
| Key pair | the project key pair |
| Storage | **30 GiB `gp3`** root volume |
| Advanced → Auto-assign public IP | yes (temporary) |

Attach a **Security Group** you create next (step 3) — do not use the
launch wizard default.

### Time sync

EC2 syncs via the **Amazon Time Sync Service** automatically, so no NTP
config is needed and the `<time>` in logs is trustworthy. Confirm after
boot:

```bash
timedatectl
# should be: active, and "System clock synchronized: yes"
```

---

## 2. Allocate an Elastic IP

A stopped instance **loses its public IP** and gets a new one on start.
Every attack-sim script and the firewall treat the IP as the target, so
assign an Elastic IP:

1. EC2 → **Elastic IPs** → Allocate.
2. Associate it with `mini-soc`.
| Property | Value |
|---|---|
| Change on `stop`/`start` | with Elastic IP: none |

Record the Elastic IP — it goes into `attack-sim/target.conf` on your Kali
VM (`ALLOWED_TARGET`).

> An Elastic IP attached to a *running* instance is free; an EIP with no
> running instance is billed. That's part of why step 10 says stop, not
> terminate.

---

## 2. Security Group

Edit the instance's Security Group to match exactly
`infrastructure/ec2-soc/security-group.json`:

| Direction | Protocol | Port | Source / destination | Why |
|---|---|---|---|---|
| Inbound | tcp | 22 | `0.0.0.0/0` | SSH + the SSH brute-force demo |
| Inbound | tcp | 80 | `0.0.0.0/0` | DVWA — the web-attack target |
| Inbound | tcp | **443** | `<YOUR_IP>/32` | SOC dashboard/API — **not** world-open |
| Outbound | all | — | `0.0.0.0/0` | package installs; `SOC_OUT:` logging on the host |

Everything else stays closed. The Security Group is the outer layer;
nftables (installed in step 6) is the inner layer and what the IDS reads.

---

## 3. Connect

```bash
chmod 400 mini-soc.pem
ssh -i mini-soc.pem ubuntu@<elastic-ip>
```

---

## 4. Base packages

```bash
sudo apt-get update
sudo apt-get install -y git curl ca-certificates
```

Everything else the SOC needs (nftables, Python 3.11+, Node 20,
PostgreSQL 16, nginx, the systemd units) is installed by
`deploy/install.sh` in step 6 — don't hand-install those.

---

## 5. Clone the repo

```bash
git clone https://github.com/Kelben-ui/mini-soc.git /home/ubuntu/mini-soc
cd /home/ubuntu/mini-soc
```

---

## 6. Provision the SOC stack

One idempotent command:

```bash
sudo bash /home/ubuntu/mini-soc/deploy/install.sh
```

It does all of: OS packages incl. nftables, Node 20, the checkout/venv,
service users + directories, **PostgreSQL 16** (PGDG repo, role,
database), Alembic migrations, the frontend build, the systemd units, the
**nginx site + self-signed TLS cert**, the **IDS config + allow-list +
`soc-block` + sudoers**, the **host firewall `/etc/nftables.conf`**, and
service start.

Then verify:

```bash
systemctl status soc-backend soc-collector soc-detection soc-agent mini-soc-ids postgresql nginx
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/     # expect 200
```

Answer the two questions the installer asks about the dashboard domain
and analyst IP(s); the analyst IP is what 443 is meant to be reached from.

---

## 7. DVWA (the web target)

DVWA is deliberately *not* automated by `install.sh` — it is the
intentionally-vulnerable target and its config is a lab artifact
(`infrastructure/ec2-soc/nginx/dvwa.conf`,
`.../php-fpm/www.conf`, `.../dvwa/config.inc.php`).

```bash
# 7a. PHP + MariaDB (nginx already came from install.sh)
sudo apt-get install -y mariadb-server \
    php8.3-fpm php8.3-mysql php8.3-gd php8.3-curl php8.3-xml php8.3-mbstring

# 7b. database + app user
sudo mariadb -e "CREATE DATABASE dvwa;
  CREATE USER 'dvwa'@'localhost' IDENTIFIED BY '<SET-A--PASSWORD>';
  GRANT ALL ON dvwa.* TO 'dvwa'@'localhost';
  FLUSH PRIVILEGES;"

# 7c. the app
sudo git clone https://github.com/digininja/DVWA /var/www/dvwa
sudo cp /var/www/dvwa/config/config.inc.php.dist \
        /var/www/dvwa/config/config.inc.php
```

Edit `/var/www/dvwa/config/config.inc.php` to the values in
`infrastructure/ec2-soc/dvwa/config.inc.php` (`db_user = dvwa`,
`db_password = <the one you set>`, `db_port = 3306`), then:

```bash
sudo chown -R www-data:www-data /var/www/dvwa
sudo tee /etc/nginx/sites-available/dvwa.conf >/dev/null <<'EOF'
# (copy from infrastructure/ec2-soc/nginx/dvwa.conf)
EOF
sudo ln -sf /etc/nginx/sites-available/dvwa.conf /etc/nginx/sites-enabled/dvwa.conf
sudo nginx -t && sudo systemctl reload nginx
```

Finish the install in the browser:

1. `http://<elastic-ip>/dvwa/setup.php` → **Create / Reset Database**.
2. Log in (`admin` / `password`).
3. **DVWA Security → Low** — the scripts assume low, and low is what the
   rules are tuned against.

---

## 8. Users

| User | Purpose | Notes |
|---|---|---|
| `ubuntu` | admin / analyst | default EC2 user |
| `testuser` | SSH brute-force target | weak password, on purpose |

```bash
sudo adduser --disabled-password --gecos "" testuser
printf 'testuser:realpassword\n' | sudo chpasswd
```

`sshd_config` keeps `PasswordAuthentication yes` for exactly this account;
everything else follows `infrastructure/ec2-soc/sshd_config`.

---

## 9. Verify the detects-on-nothing baseline

```bash
# the IDS should be quiet
sudo tail -n 5 /var/log/mini_soc_IDS.json 2>/dev/null || true
# the firewall ruleset that the IDS parses should be loaded
sudo nft list ruleset | grep -E 'SOC_(DROP|ACCEPT|OUT)'
# the allow-list should hold the analyst IP
sudo cat /etc/mini-soc/allowlist.txt
```

Do **not** start an attack here — this just proves a clean install.

---

## 10. Snapshot the "clean baseline"

Before any test traffic mutates the database:

1. **EC2 → Instances → mini-soc → Actions → Image and templates → Create
   image**, name it `mini-soc-clean-baseline`.
2. Wait for the AMI to become `available` (Images → AMIs).

That AMI is the reproducible clean install, replacing the old VM
snapshots. Launch a demo instance from it rather than re-running this
page, and treat *this* page as the "rebuild from nothing" fallback.

## 10. Stop when idle

The instance costs by the hour while running:

```bash
# stop, keep the root volume + Elastic IP
aws ec2 stop-instances --instance-ids <id>
# or: EC2 console → Instance state → Stop
```

Stopping keeps the EBS root volume and the Elastic IP; it stops compute
charges. **Terminate** only when you want it gone (this deletes the root
volume unless you snapshot).

---

## Troubleshooting

| Symptom | First thing to check |
|---|---|
| Dashboard unreachable | your current IP vs the SG 443 rule (`curl ifconfig.me`), `nginx -t` |
| No alerts at all | `soc-agent`/`soc-collector`/`soc-detection` unit status; is the firewall loaded (`nft list ruleset`)? |
| Web rules never fire | nginx is using the `soc` log format (`infrastructure/ec2-soc/nginx/nginx.conf`); collector is tailing `/var/log/nginx/access.log` |
| Brute-force test won't connect | SG allows 22; sshd `PasswordAuthentication yes`; `AllowUsers` includes `testuser` |
| Postgres won't start | `install.sh` step: PGDG repo + `postgresql.service`; check `journalctl -u postgresql` |

See also: `docs/architecture.md` §4, `docs/testing/test-plan.md`,
`docs/testing/pre-session-checklist.md`.
