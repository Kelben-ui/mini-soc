# Log Agent — EC2 Test Guide

End-to-end verification of the host log agent (`agents/log_agent/`) on the Mini
SOC EC2 instance, covering the Phase 3 requirements (tasks 3.1–3.9) plus a
hardening pass (step 11).

The agent ships logs; the **collector** parses them. A `422` from the collector
means "batch received, but no line in it parsed" — that is a parser/format
issue, not an agent failure. The agent treats every response `< 500` as
delivered (`agents/log_agent/sender.py`), so `422`/`4xx` batches are dropped,
not retried.

Run everything on the box. The ingest header is **`X-API-Key`** (the code uses
this; some older docs said `X-Ingest-Key`).

---

## 0. Setup

```bash
ssh ubuntu@<EC2-ELASTIC-IP>
cd /home/ubuntu/mini-soc

# pytest is a dev dependency; install.sh installs requirements.txt only.
.venv/bin/pip install -r requirements-dev.txt

# Read-only event-count helper. Re-define it after every new SSH session
# (shell functions do not persist across sessions).
count() { sudo -u postgres psql -tA -d mini_soc -c "select count(*) from events where log_type='$1'"; }
```

## 1. Unit tests (tasks 3.1–3.9)

```bash
.venv/bin/python -m pytest agents -q
```
Expected:
```
16 passed in 0.xx s
```

## 2. Service, privileges, config (tasks 3.1, 3.8)

```bash
systemctl is-active soc-agent soc-collector soc-backend
```
```
active
active
active
```

```bash
systemctl show soc-agent -p User -p SupplementaryGroups -p NoNewPrivileges -p ProtectSystem
```
```
User=mini-soc
SupplementaryGroups=adm mini-soc-ids systemd-journal
NoNewPrivileges=yes
ProtectSystem=strict
```

```bash
ps -o user=,cmd= -p "$(systemctl show -p MainPID --value soc-agent)"
```
```
mini-soc /home/ubuntu/mini-soc/.venv/bin/python -m agents.log_agent.agent
```

```bash
sudo cat /etc/mini-soc/agent.yaml
```
Expect the 4 file sources (`nginx_access`, `nginx_error`, `auth`,
`mini_soc_ids`) and 1 journal source (`firewall`, `args: ["-k"]`).

> The agent's startup banner is a plain `print()` captured by journald through a
> pipe, so it is block-buffered and may not appear promptly. Verify liveness via
> the process (`ps`) and the functional tests below, not the banner.

## 3. End-to-end: file → collector → DB

```bash
before=$(count nginx_access); curl -sk "https://localhost/agent-test-$(date +%s)" -o /dev/null; sleep 5; echo "before=$before after=$(count nginx_access)"
```
```
before=123 after=124
```
Pass = exactly `before + 1`.

## 4. Restart resumes exactly (task 3.2)

```bash
before=$(count nginx_access)
sudo systemctl restart soc-agent
sleep 3
echo "after restart: $(count nginx_access) (expected $before)"
curl -sk https://localhost/agent-restart -o /dev/null
sleep 5
echo "after new line: $(count nginx_access) (expected $((before+1)))"
```
```
after restart: 124 (expected 124)
after new line: 125 (expected 125)
```

## 5. Rotation + truncation (task 3.3)

```bash
sudo logrotate -f /etc/logrotate.d/nginx
curl -sk https://localhost/agent-rotate -o /dev/null
sleep 5
sudo truncate -s 0 /var/log/nginx/access.log
curl -sk https://localhost/agent-truncate -o /dev/null
sleep 5
echo "total now: $(count nginx_access)"   # +2 vs step 4
sudo cat /var/lib/mini-soc/agent/state.json
```
The `access.log` entry's `inode` changes after rotation.

## 6. Batching (task 3.4) — needs a 2nd terminal

Terminal 2: `journalctl -u soc-collector -f`

Terminal 1:
```bash
for i in 1 2 3; do curl -sk "https://localhost/batch-$i" -o /dev/null; done
```
Expected: **one** `POST /ingest ... 200`, not three (the lines coalesce within
`batch.max_seconds: 2`).

## 7. Collector down → spool → replay (task 3.5)

```bash
sudo systemctl stop soc-collector
curl -sk https://localhost/agent-spool-test -o /dev/null
sleep 5
sudo cat /var/lib/mini-soc/agent/spool/batches.jsonl   # the batch is spooled
sudo systemctl start soc-collector
sleep 8
sudo ls -l /var/lib/mini-soc/agent/spool/batches.jsonl
```
```
ls: cannot access '/var/lib/mini-soc/agent/spool/batches.jsonl': No such file or directory
```
(The file is removed once the spool drains.)

## 8. Kernel journal / firewall source (task 3.6)

```bash
echo "SOC_DROP: IN=eth0 OUT= SRC=203.0.113.77 DST=172.31.13.199 PROTO=TCP SPT=40000 DPT=1234 SYN" | sudo tee /dev/kmsg
sleep 5
count firewall
sudo ls -l /var/lib/mini-soc/agent/journal-kernel.cursor
```

## 9. Heartbeat + IDS status (task 3.7)

```bash
sudo -u postgres psql -x -d mini_soc -c "select name,host,status,last_heartbeat,details from agents where name='log-agent';"
```
```
name           | log-agent
host           | ip-172-31-13-199
status         | online
last_heartbeat | 2026-10-14 12:00:30.123456+00
details        | {"ids": {"service": "mini-soc-ids", "status": "active"}}
```

## 10. Ingest auth

```bash
key=$(sudo grep -E '^INGEST_API_KEY=' /etc/mini-soc/.env | cut -d= -f2-)
curl -s -o /dev/null -w 'bad  -> %{http_code}\n' -X POST http://127.0.0.1:9000/ingest -H 'X-API-Key: wrong' -H 'Content-Type: application/json' -d '{"host":"t","log_type":"auth","lines":["x"]}'
curl -s -o /dev/null -w 'good -> %{http_code}\n' -X POST http://127.0.0.1:9000/ingest -H "X-API-Key: $key" -H 'Content-Type: application/json' -d '{"host":"t","log_type":"auth","lines":["Oct 14 12:00:00 host sshd[1]: Failed password for test from 203.0.113.5 port 40000 ssh2"]}'
```
```
bad  -> 401
good -> 200
```

---

## 11. Hardening checks

Not required for the task sign-off, but they close the gaps a smoke test leaves.

### 11.1 Size-based batching (`batch.max_lines`)

Only the time flush is exercised in step 6. Force the size threshold (200):

```bash
# Terminal 2
journalctl -u soc-collector -f
```
```bash
for i in $(seq 1 250); do curl -sk "https://localhost/bulk-$i" -o /dev/null; done
```
Expected: a handful of `POST` lines, **not ~250** — the 200-line threshold fires
before the per-request time flush can. (Some time flushes may interleave; the
point is that far fewer POSTs than lines are sent.)

### 11.2 Sustained outage → FIFO + backoff

```bash
sudo systemctl stop soc-collector
for i in 1 2 3; do curl -sk "https://localhost/outage-$i" -o /dev/null; sleep 3; done
sudo cat /var/lib/mini-soc/agent/spool/batches.jsonl   # 3 batches, oldest first
sudo systemctl start soc-collector
sleep 25
sudo ls -l /var/lib/mini-soc/agent/spool/batches.jsonl # gone
```
Expected: all three batches spool (order preserved, `created` increasing) and
replay oldest-first after recovery.

### 11.3 Crash (SIGKILL) durability

`systemctl restart` is a graceful SIGTERM (final flush). Test an ungraceful kill:

```bash
before=$(count nginx_access)
sudo systemctl kill -s SIGKILL soc-agent
sudo systemctl start soc-agent
sleep 3
echo "after crash restart: $(count nginx_access) (expected $before)"
curl -sk https://localhost/agent-postkill -o /dev/null
sleep 5
echo "after new line: $(count nginx_access) (expected $((before+1)))"
```
Expected: no duplication after restart, and a new line is ingested exactly once.
Note the tradeoff: a line read into the in-memory batch within
`batch.max_seconds` of the kill can be lost (offset already advanced). That is
expected for an ungraceful kill; the guarantee is no loss/dup for lines already
delivered.

### 11.4 Reboot persistence

```bash
systemctl is-enabled soc-agent soc-collector soc-backend
sudo reboot
# reconnect after ~30s
systemctl is-active soc-agent soc-collector soc-backend
```

### 11.5 Spool write failure (review only)

If the spool cannot be written (disk full), `Spooler.enqueue()` raises and the
exception is caught by the tailer worker, dropping that batch. There is no
metric/alert for this. Safe to reason about, not to force on a live box.

### 11.6 Long-run stability

Watch over time / after repeated rotations:

```bash
journalctl -u soc-agent --since "1 hour ago" --no-pager | grep -i error
ls /proc/"$(systemctl show -p MainPID --value soc-agent)"/fd | wc -l   # fd count should stay flat
```

---

## Format assumptions (Ubuntu 24.04)

If a source shows `FAIL` in the parser probe below, the box's output format
differs from what the collector expects. These were the mismatches found on the
live instance and fixed in `collector/parsers/`:

- `auth.log` uses rsyslog ISO timestamps (`2026-10-14T14:24:06.152339+00:00 …`)
  in addition to the classic `Oct 13 09:11:02 …`.
- `journalctl -o short-iso` emits an RFC 3339 offset with a colon
  (`+00:00`), not the compact `+0000`.
- Anonymous nginx requests leave `$remote_user` **empty** (`<ip> -  [iso=…]`),
  not `-`.
- The :80 redirect server must log in the `soc` format so it does not write
  `combined` lines into the soc access log.

Probe each source with the real collector parser:

```bash
sudo .venv/bin/python - <<'PY'
import subprocess
from collector.main import PARSERS
files = {
    "nginx_access": "/var/log/nginx/access.log",
    "nginx_error": "/var/log/nginx/error.log",
    "auth": "/var/log/auth.log",
    "mini_soc_ids": "/var/log/mini_soc_ids.json",
}
for lt, path in files.items():
    try:
        lines = open(path, errors="replace").read().splitlines()
    except OSError as e:
        print(f"{lt:14} SKIP  {e}"); continue
    if not lines:
        print(f"{lt:14} EMPTY"); continue
    line = lines[-1]
    print(f"{lt:14} {'OK' if PARSERS[lt](line) else 'FAIL'}  {line[:110]}")
fw = subprocess.run(["journalctl","-k","-o","short-iso","-n","1"],
                    capture_output=True, text=True).stdout.strip().splitlines()
if fw:
    print(f"{'firewall':14} {'OK' if PARSERS['firewall'](fw[-1]) else 'FAIL'}  {fw[-1][:110]}")
PY
```

---

## Pass criteria

| Area | Task | Pass |
|---|---|---|
| Config drives sources, nothing hard-coded | 3.1 | ☐ |
| Offsets persist; restart loses/dups nothing | 3.2 | ☐ |
| Rotation + truncation lose no line | 3.3 | ☐ |
| Batching (time and size) | 3.4 | ☐ |
| Spool + FIFO replay with backoff | 3.5 | ☐ |
| Kernel journal firewall stream + cursor | 3.6 | ☐ |
| Heartbeat + IDS status reflected | 3.7 | ☐ |
| Runs unprivileged, hardened unit | 3.8 | ☐ |
| Unit suite green | 3.9 | ☐ |
| Hardening (11.1–11.4) | — | ☐ |

## Known by-design behaviours

- The `firewall` source streams **all** kernel messages (`journalctl -k -f`), but
  only `SOC_DROP:`/`SOC_ACCEPT:`/`SOC_OUT:` lines parse. A batch containing only
  other kernel lines returns `422` and is dropped. This is expected noise, not
  an error.
- Any `< 500` response (including `422`/`4xx`) is treated as delivered, so
  unparseable lines are dropped rather than retried. There is no dropped-line
  counter.
