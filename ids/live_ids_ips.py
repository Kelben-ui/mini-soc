#!/usr/bin/env python3
"""Mini SOC IDS (task 4.1-4.9).

Detection-only daemon that replaces Suricata.  It reads the systemd journal
(nftables firewall lines, SSH authentication failures) and optionally sniffs
UDP/53 DNS queries, then writes one JSON alert/event per line to
``mini_soc_ids.json`` (``output.path`` / ``$IDS_OUTPUT``).  The log agent
forwards that file to the collector, which normalizes it into the common event
model (contracts 2.6).

Detection is **detection-only**: this daemon never modifies the firewall.
Prevention (the ``soc-block`` helper, task 4.7) is driven by the backend after
analyst confirmation.

Run as a module (repo root on sys.path) or as a script::

    python -m ids.live_ids_ips

Reading the systemd journal needs either root or membership in the
``systemd-journal`` group; the packaged unit grants ``systemd-journal`` and
``adm``.  Sniffing DNS needs ``CAP_NET_RAW`` and is disabled with
``dns.enabled: false``.

Every threshold, window, allow-list entry, output path and signature comes from
``ids.yaml`` (see ``ids/README.md``); nothing is hard-coded here.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:  # `python -m ids.live_ids_ips`
    from ids.config import IdsConfig, load_config
    from ids.dns_sniffer import sniff as sniff_dns
except ImportError:  # pragma: no cover - `python ids/live_ids_ips.py`
    from config import IdsConfig, load_config
    from dns_sniffer import sniff as sniff_dns


# --- Log line parsing -------------------------------------------------------

_FIELD = re.compile(r"\b(SRC|DST|SPT|DPT)=(\S+)")
_PROTO = re.compile(r"\bPROTO=(\S+)")
_SSH_FROM = re.compile(r"from ([0-9A-Fa-f:.]+)")
_SSH_PORT = re.compile(r"port (\d+)")
_SYN = re.compile(r"\bSYN\b")

KINDS_WITH_PORTS = {"scan", "outbound", "syn_flood"}

# Seconds to wait before retrying the DNS sniffer after a socket error.
RETRY_SEC = 5


def _local_ip() -> str:
    import socket

    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "0.0.0.0"


LOCAL_IP = _local_ip()


def parse_line(line: str, config: IdsConfig):
    """Parse one journal line into a detection dict, or ``None``.

    Returns ``{kind, src_ip, dest_ip, src_port, dest_port, proto, syn}`` where
    ``kind`` is one of ``scan``, ``outbound`` or ``ssh``.
    """
    line = (line or "").strip()

    if not line:
        return None

    probe_marker = any(marker in line for marker in config.nmap_probe_markers)

    if config.soc_drop_prefix in line or probe_marker:
        return _parse_firewall(line, "scan")

    if config.soc_out_prefix in line:
        return _parse_firewall(line, "outbound")

    if "Failed password" in line:
        src = _SSH_FROM.search(line)
        port = _SSH_PORT.search(line)

        if src:
            return {
                "kind": "ssh",
                "src_ip": src.group(1),
                "dest_ip": LOCAL_IP,
                "src_port": int(port.group(1)) if port else None,
                "dest_port": 22,
                "proto": "TCP",
                "syn": False,
            }

    return None


def _parse_firewall(line: str, kind: str):
    fields = dict(_FIELD.findall(line))

    src = fields.get("SRC")
    dst = fields.get("DST")

    if not src:
        return None

    spt = fields.get("SPT")
    dpt = fields.get("DPT")
    proto = _PROTO.search(line)

    return {
        "kind": kind,
        "src_ip": src,
        "dest_ip": dst or LOCAL_IP,
        "src_port": int(spt) if spt and spt.isdigit() else None,
        "dest_port": int(dpt) if dpt and dpt.isdigit() else None,
        "proto": proto.group(1) if proto else "TCP",
        "syn": bool(_SYN.search(line)),
    }


def now_eve() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+0000")


def _max_label_len(qname: str) -> int:
    return max((len(label) for label in qname.split(".")), default=0)


def _item_time(item):
    """Stores hold either ``(timestamp, ...)`` tuples or bare timestamps."""
    return item[0] if isinstance(item, tuple) else item


# --- Detection engine -------------------------------------------------------


class IdsEngine:
    """Stateful, thread-safe detector.

    ``process_line`` / ``process_dns`` are pure enough to unit test: they
    return the events they wrote (if any) and accept an explicit ``now`` clock.
    """

    def __init__(self, config: IdsConfig):
        self.config = config

        self.scan_hits: dict[str, deque] = defaultdict(deque)
        self.ssh_hits: dict[str, deque] = defaultdict(deque)
        self.syn_hits: dict[str, deque] = defaultdict(deque)
        self.dns_hits: dict[str, deque] = defaultdict(deque)
        self.last_alert: dict[tuple, float] = {}
        self.recent_lines: dict[str, float] = {}

        self._lock = threading.Lock()
        self._last_prune = 0.0

    # --- help ---------------------------------------------------------------

    def is_allowlisted(self, ip: str) -> bool:
        return ip in self.config.allowlist

    def _cooldown_ok(self, ip: str, kind: str, now: float) -> bool:
        last = self.last_alert.get((ip, kind))

        if last is None:
            return True

        return (now - last) >= self.config.cooldown_sec

    def _window_threshold(self, kind: str):
        if kind == "scan":
            return self.config.scan_window_sec, self.config.scan_threshold
        if kind == "ssh":
            return self.config.ssh_window_sec, self.config.ssh_threshold
        if kind == "syn_flood":
            return self.config.syn_window_sec, self.config.syn_threshold
        raise KeyError(kind)

    # --- counters -----------------------------------------------------------

    def _track_ports(self, store, ip, now, window, threshold, dest_port):
        q = store[ip]
        q.append((now, dest_port))

        while q and now - q[0][0] > window:
            q.popleft()

        distinct = {port for _, port in q if port is not None}
        count = len(distinct) if dest_port is not None else len(q)

        return count >= threshold, count, q

    def _track_times(self, store, ip, now, window, threshold):
        q = store[ip]
        q.append(now)

        while q and now - q[0] > window:
            q.popleft()

        return len(q) >= threshold, len(q), q

    # --- event builders -----------------------------------------------------

    def _base_event(self, kind, info, count, raw, event_type="alert"):
        sig = self.config.signature(kind)

        return {
            "timestamp": now_eve(),
            "event_type": event_type,
            "host": self.config.hostname,
            "src_ip": info["src_ip"],
            "src_port": info.get("src_port"),
            "dest_ip": info.get("dest_ip"),
            "dest_port": info.get("dest_port"),
            "proto": info.get("proto", "TCP"),
            "alert": {
                "action": "allowed",
                "gid": 1,
                "signature_id": sig["id"],
                "rev": 1,
                "signature": sig["msg"],
                "category": sig["category"],
                "severity": sig["priority"],
            },
            "metadata": {"count": count},
            "raw": raw,
        }

    def _dns_event(self, qname, src_ip, count, raw):
        sig = self.config.signature("dns")

        return {
            "timestamp": now_eve(),
            "event_type": "dns_query",
            "host": self.config.hostname,
            "src_ip": src_ip,
            "src_port": None,
            "dest_ip": None,
            "dest_port": 53,
            "proto": "UDP",
            "alert": {
                "action": "allowed",
                "gid": 1,
                "signature_id": sig["id"],
                "rev": 1,
                "signature": sig["msg"],
                "category": sig["category"],
                "severity": sig["priority"],
            },
            "metadata": {"count": count},
            "dns": {"qname": qname, "length": len(qname)},
            "raw": raw,
        }

    # --- processing ---------------------------------------------------------

    def process_line(self, line: str, now: float | None = None) -> list:
        """Parse and evaluate one journal line; return the events written."""
        if not line:
            return []

        now = time.time() if now is None else now
        info = parse_line(line, self.config)

        if not info:
            return []

        ip = info["src_ip"]

        if self.is_allowlisted(ip):
            return []

        # Ignore the same log line delivered twice within a second.
        line_key = line.strip()
        if now - self.recent_lines.get(line_key, 0) < 1:
            return []

        self.recent_lines[line_key] = now
        if len(self.recent_lines) > 5000:
            self.recent_lines.clear()

        events = []

        with self._lock:
            kind = info["kind"]

            if kind == "scan":
                window, threshold = self._window_threshold("scan")
                triggered, count, q = self._track_ports(
                    self.scan_hits, ip, now, window, threshold, info["dest_port"]
                )

                if triggered and self._cooldown_ok(ip, "scan", now):
                    events.append(self._base_event("scan", info, count, line.strip()))
                    self.last_alert[(ip, "scan")] = now
                    q.clear()

                if info.get("syn"):
                    swindow, sthreshold = self._window_threshold("syn_flood")
                    triggered, count, q = self._track_times(
                        self.syn_hits, ip, now, swindow, sthreshold
                    )

                    if triggered and self._cooldown_ok(ip, "syn_flood", now):
                        events.append(
                            self._base_event("syn_flood", info, count, line.strip())
                        )
                        self.last_alert[(ip, "syn_flood")] = now
                        q.clear()

            elif kind == "ssh":
                window, threshold = self._window_threshold("ssh")
                triggered, count, q = self._track_times(
                    self.ssh_hits, ip, now, window, threshold
                )

                if triggered and self._cooldown_ok(ip, "ssh", now):
                    events.append(self._base_event("ssh", info, count, line.strip()))
                    self.last_alert[(ip, "ssh")] = now
                    q.clear()

            elif kind == "outbound":
                if (
                    info["dest_port"] is not None
                    and info["dest_port"] not in self.config.outbound_allow
                    and self._cooldown_ok(ip, "outbound", now)
                ):
                    events.append(
                        self._base_event(
                            "outbound",
                            info,
                            1,
                            line.strip(),
                            event_type="outbound_connection",
                        )
                    )
                    self.last_alert[(ip, "outbound")] = now

            self._write(events)
            self._prune(now)

        return events

    def process_dns(self, qname: str, src_ip: str, now: float | None = None) -> list:
        """Evaluate one observed DNS query; return the events written."""
        if not qname or self.is_allowlisted(src_ip):
            return []

        now = time.time() if now is None else now

        with self._lock:
            q = self.dns_hits[src_ip]
            q.append((now, qname, _max_label_len(qname)))

            while q and now - q[0][0] > self.config.dns_window_sec:
                q.popleft()

            count = len(q)
            longest = max((item[2] for item in q), default=0)

            long_label = longest > self.config.dns_max_label_len
            high_rate = count > self.config.dns_rate_per_min

            events = []

            if (long_label or high_rate) and self._cooldown_ok(
                src_ip, "dns", now
            ):
                raw = (
                    f"qname={qname} length={len(qname)} rate={count} "
                    f"longest_label={longest}"
                )
                events.append(self._dns_event(qname, src_ip, count, raw))
                self.last_alert[(src_ip, "dns")] = now

            self._write(events)
            self._prune(now)

        return events

    # --- output + memory hygiene -------------------------------------------

    def _write(self, events):
        for event in events:
            try:
                with open(self.config.output_path, "a") as handle:
                    handle.write(json.dumps(event) + "\n")
            except OSError as error:
                print(f"[ERROR] Could not write alert: {error}", flush=True)
                continue

            sig = event["alert"]["signature"]
            src = event.get("src_ip") or event["dns"]["qname"]
            print(f"[ALERT] {sig} from {src} (count={event['metadata']['count']})", flush=True)

    def _prune(self, now: float):
        if now - self._last_prune < self.config.prune_interval_sec:
            return

        self._last_prune = now

        stores = [
            (self.scan_hits, self.config.scan_window_sec),
            (self.ssh_hits, self.config.ssh_window_sec),
            (self.syn_hits, self.config.syn_window_sec),
            (self.dns_hits, self.config.dns_window_sec),
        ]

        for store, window in stores:
            for ip in list(store):
                q = store[ip]

                while q and now - _item_time(q[0]) > window:
                    q.popleft()

                if not q:
                    del store[ip]

        for key in list(self.last_alert):
            if now - self.last_alert[key] > self.config.idle_ttl_sec:
                del self.last_alert[key]

        for line in list(self.recent_lines):
            if now - self.recent_lines[line] > 60:
                del self.recent_lines[line]


# --- Runtime ----------------------------------------------------------------


def monitor_journal(engine: IdsEngine, config: IdsConfig):
    cmd = ["journalctl", *config.journal_args]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )

    try:
        for line in process.stdout:
            engine.process_line(line)
    finally:
        process.terminate()


def run_dns_sniffer(engine: IdsEngine, config: IdsConfig, stop_event):
    """Sniff DNS queries until ``stop_event`` is set.

    A socket error must not silently kill DNS detection: the thread logs the
    error and retries every ``RETRY_SEC`` seconds, so a transient failure (or
    an interface that only appears later) does not leave the SOC blind.
    """

    def handle(packet):
        engine.process_dns(packet["qname"], packet["src_ip"])

    while not stop_event.is_set():
        try:
            sniff_dns(handle, config.dns_interface, stop_event.is_set)
        except PermissionError:
            print(
                "[ERROR] Cannot sniff DNS: CAP_NET_RAW is required. "
                "Set dns.enabled: false in ids.yaml to run without it.",
                flush=True,
            )
            return
        except OSError as error:
            print(
                f"[ERROR] DNS sniffer stopped: {error} - retrying in {RETRY_SEC}s",
                flush=True,
            )
            if stop_event.wait(RETRY_SEC):
                return
        else:
            return


def has_journal_access() -> bool:
    """Return True when journalctl can be read (root or systemd-journal group)."""
    try:
        subprocess.run(
            ["journalctl", "-n", "0", "-o", "short-iso"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def main():
    config = load_config()

    if not has_journal_access():
        print(
            "[ERROR] Cannot read the systemd journal. Run as root or add the "
            "service account to the systemd-journal group.",
            flush=True,
        )
        return 1

    engine = IdsEngine(config)

    print("[*] Mini SOC IDS (detection only) started", flush=True)
    print(f"[*] Host: {config.hostname}", flush=True)
    print(f"[*] Writing alerts to {config.output_path}", flush=True)
    print(f"[*] Allow-list: {sorted(config.allowlist) or 'empty'}", flush=True)

    stop_event = threading.Event()

    if config.dns_enabled:
        print("[*] DNS sniffer enabled (CAP_NET_RAW)", flush=True)
        threading.Thread(
            target=run_dns_sniffer,
            args=(engine, config, stop_event),
            daemon=True,
        ).start()
    else:
        print("[*] DNS sniffer disabled", flush=True)

    try:
        monitor_journal(engine, config)
    except KeyboardInterrupt:
        print("\n[INFO] IDS stopped.", flush=True)
    finally:
        stop_event.set()

    return 0


if __name__ == "__main__":
    sys.exit(main())
