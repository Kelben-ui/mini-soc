"""Log agent: tails log files and forwards raw lines to the collector.

When the collector/backend is down the agent spools the raw lines to disk
(AGENT_SPOOL_DIR) and replays them once the collector is reachable again,
so no log data is lost during a backend outage.

Run as a module so the repo root is importable::

    python -m agents.log_agent.agent

Watched sources (log_type):
    /var/log/nginx/access.log       nginx_access
    /var/log/nginx/error.log        nginx_error
    /var/log/auth.log               auth
    /var/log/mini_soc_ids.json      mini_soc_ids
    /var/log/kern.log               firewall
"""

import os
import threading
import time

import requests

from mini_soc_config import get_env, spool_dir


COLLECTOR_URL = get_env("COLLECTOR_URL", "http://127.0.0.1:9000/ingest")
SPOOL_DIR = str(spool_dir())

LOG_FILES = {
    "/var/log/nginx/access.log": "nginx_access",
    "/var/log/nginx/error.log": "nginx_error",
    "/var/log/auth.log": "auth",
    "/var/log/mini_soc_ids.json": "mini_soc_ids",
    "/var/log/kern.log": "firewall",
}


def spool_path(log_type):
    return f"{SPOOL_DIR}/{log_type}.spool"


def queue_line(log_type, line):
    """Buffer a raw line that could not be delivered."""
    try:
        os.makedirs(SPOOL_DIR, exist_ok=True)

        with open(spool_path(log_type), "a", encoding="utf-8") as f:
            f.write(line + "\n")

    except OSError as exc:
        print(f"[agent] could not buffer {log_type} line: {exc}")


def send_line(log_type, line):
    response = requests.post(
        COLLECTOR_URL,
        json={"log_type": log_type, "raw": line},
        timeout=5
    )
    return response.status_code < 500


def drain_spool(log_type):
    """Replay spooled lines, keeping only the ones still failing."""
    path = spool_path(log_type)

    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f if ln.strip()]

    kept = []

    for line in lines:
        try:
            ok = send_line(log_type, line)
        except Exception:
            ok = False

        print(f"{log_type} spool replay: {'ok' if ok else 'kept'} {line[:80]}")

        if not ok:
            kept.append(line)

    if kept:
        with open(path, "w", encoding="utf-8") as f:
            for line in kept:
                f.write(line + "\n")
    else:
        try:
            os.remove(path)
        except OSError:
            pass


def watch_log(log_file, log_type):
    f = None

    while f is None:
        try:
            f = open(log_file, "r", encoding="utf-8", errors="replace")
        except FileNotFoundError:
            print(f"[agent] {log_file} not found yet; waiting...")
            time.sleep(5)

    f.seek(0, 2)

    while True:
        line = f.readline()

        if not line:
            time.sleep(1)
            continue

        line = line.strip()

        if not line:
            continue

        try:
            ok = send_line(log_type, line)
        except Exception as exc:
            print(f"{log_type} send error: {exc}")
            ok = False

        if ok:
            print(f"{log_type} sent ok")
            drain_spool(log_type)
        else:
            print(f"{log_type} backend down; buffering line")
            queue_line(log_type, line)


def main():
    os.makedirs(SPOOL_DIR, exist_ok=True)

    threads = []

    for log_file, log_type in LOG_FILES.items():
        thread = threading.Thread(
            target=watch_log,
            args=(log_file, log_type),
            daemon=True
        )
        thread.start()
        threads.append(thread)

    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
