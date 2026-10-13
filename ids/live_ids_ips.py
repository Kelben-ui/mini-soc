#!/usr/bin/env python3
"""Mini SOC IDS (detection only). Writes alerts to /var/log/mini_soc_ids.json

Run as a module (repo root on sys.path) or as a script::

    python -m ids.live_ids_ips

Reading the systemd journal needs either root or membership in the
``systemd-journal`` group; the packaged unit grants that group.
"""
import subprocess
import re
import sys
import time
import os
import json
import socket
from collections import defaultdict, deque
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mini_soc_config import get_env, get_int  # noqa: E402

# Config via env (systemd EnvironmentFile) or ids.yaml; defaults match spec
EVE_FILE = get_env("IDS_OUTPUT", "/var/log/mini_soc_ids.json")
HOSTNAME = get_env("SOC_HOSTNAME", "fw-01")
WHITELIST = set(
    ip.strip() for ip in (get_env("IDS_ALLOWLIST", "") or "").split(",") if ip.strip()
)

SCAN_PORTS = get_int("IDS_SCAN_THRESHOLD", 15)
SCAN_WINDOW = get_int("IDS_SCAN_WINDOW_SEC", 60)
SSH_THRESHOLD = get_int("IDS_SSH_THRESHOLD", 10)
SSH_WINDOW = get_int("IDS_SSH_WINDOW_SEC", 300)
COOLDOWN = get_int("IDS_COOLDOWN_SEC", 60)

try:
    LOCAL_IP = socket.gethostbyname(socket.gethostname())
except Exception:
    LOCAL_IP = "0.0.0.0"

SIGNATURES = {
    "scan": {"id": 9000001, "msg": "MINI-SOC Port Scan Detected",
             "category": "Attempted Information Leak", "severity": 2},
    "ssh": {"id": 9000002, "msg": "MINI-SOC SSH Brute Force Detected",
            "category": "Attempted User Privilege Gain", "severity": 1},
}

scan_hits = defaultdict(deque)
ssh_hits = defaultdict(deque)
last_alert = {}
recent_lines = {}


def now_eve():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+0000")


def parse_line(line):
    if "NMAP_SCAN_PROBE" in line or "SOC_DROP:" in line:
        src = re.search(r"SRC=([0-9.]+)", line)
        dst = re.search(r"DST=([0-9.]+)", line)
        spt = re.search(r"SPT=(\d+)", line)
        dpt = re.search(r"DPT=(\d+)", line)
        if src and dpt:
            return {
                "kind": "scan",
                "src_ip": src.group(1),
                "dest_ip": dst.group(1) if dst else LOCAL_IP,
                "src_port": int(spt.group(1)) if spt else 0,
                "dest_port": int(dpt.group(1)),
            }
    if "Failed password" in line:
        src = re.search(r"from ([0-9.]+)", line)
        spt = re.search(r"port (\d+)", line)
        if src:
            return {
                "kind": "ssh",
                "src_ip": src.group(1),
                "dest_ip": LOCAL_IP,
                "src_port": int(spt.group(1)) if spt else 0,
                "dest_port": 22,
            }
    return None


def write_alert(kind, info, count, raw):
    sig = SIGNATURES[kind]
    event = {
        "timestamp": now_eve(),
        "event_type": "alert",
        "host": HOSTNAME,
        "src_ip": info["src_ip"],
        "src_port": info["src_port"],
        "dest_ip": info["dest_ip"],
        "dest_port": info["dest_port"],
        "proto": "TCP",
        "alert": {
            "action": "allowed",
            "gid": 1,
            "signature_id": sig["id"],
            "rev": 1,
            "signature": sig["msg"],
            "category": sig["category"],
            "severity": sig["severity"],
        },
        "metadata": {"count": count},
        "raw": raw,
    }
    try:
        with open(EVE_FILE, "a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception as e:
        print(f"[ERROR] Could not write alert: {e}")
        return
    print(f"\n[ALERT] {sig['msg']} from {info['src_ip']} (count={count})")
    print(f"        written to {EVE_FILE}\n")


def monitor_journal():
    print("[*] Mini SOC IDS (detection only) started")
    print("[*] Monitoring journal logs")
    print(f"[*] Writing alerts to {EVE_FILE}")

    cmd = ["journalctl", "-f", "-n", "0", "-o", "cat"]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True)
    try:
        for line in process.stdout:
            line = line.strip()
            now = time.time()

            info = parse_line(line)
            if not info:
                continue

            ip = info["src_ip"]
            if ip in WHITELIST:
                continue

            # ignore the same log line delivered twice
            if now - recent_lines.get(line, 0) < 1:
                continue
            recent_lines[line] = now
            if len(recent_lines) > 5000:
                recent_lines.clear()

            kind = info["kind"]

            if kind == "scan":
                q = scan_hits[ip]
                q.append((now, info["dest_port"]))
                while q and now - q[0][0] > SCAN_WINDOW:
                    q.popleft()
                count = len({p for _, p in q})
                print(f"[scan] {ip}: {count} distinct ports in window")
                triggered = count >= SCAN_PORTS
            else:
                q = ssh_hits[ip]
                q.append(now)
                while q and now - q[0] > SSH_WINDOW:
                    q.popleft()
                count = len(q)
                print(f"[ssh]  {ip}: {count} failed logins in window")
                triggered = count >= SSH_THRESHOLD

            if triggered:
                if now - last_alert.get((ip, kind), 0) >= COOLDOWN:
                    write_alert(kind, info, count, line)
                    last_alert[(ip, kind)] = now
                q.clear()

    except KeyboardInterrupt:
        print("\n[INFO] IDS stopped.")
        process.terminate()
        sys.exit(0)


def has_journal_access():
    """Return True when journalctl can be read (root or systemd-journal group)."""
    try:
        subprocess.run(
            ["journalctl", "-n", "0", "-o", "cat"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


if __name__ == "__main__":
    if not has_journal_access():
        print(
            "[ERROR] Cannot read the systemd journal. Run as root or add the "
            "service account to the systemd-journal group."
        )
        sys.exit(1)
    monitor_journal()
