"""Batching, delivery and the disk spool (tasks 3.4 and 3.5).

Lines are grouped per ``log_type`` and POSTed to the collector as a single
``{"host", "log_type", "lines": [...]}`` request - either when the batch
reaches ``max_lines`` or when ``max_seconds`` elapse, whichever comes first.

If a POST fails (connection error, timeout or a 5xx) the whole batch is
appended to a disk spool.  A background worker replays the spool oldest-first
(FIFO) with exponential backoff, so a collector outage loses nothing and order
is preserved.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import defaultdict
from pathlib import Path

import requests


class Spooler:
    """Append-only JSONL spool of batches that could not be delivered."""

    def __init__(self, path: str):
        self.path = Path(path)
        self._lock = threading.Lock()

    def enqueue(self, record: dict) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)

            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")
                handle.flush()
                os.fsync(handle.fileno())

    def read_all(self) -> list[dict]:
        with self._lock:
            if not self.path.exists():
                return []

            records: list[dict] = []

            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()

                    if not line:
                        continue

                    try:
                        records.append(json.loads(line))
                    except ValueError:
                        continue

            return records

    def rewrite(self, records: list[dict]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)

            if not records:
                try:
                    os.remove(self.path)
                except FileNotFoundError:
                    pass
                return

            tmp = self.path.with_name(self.path.name + ".tmp")

            with tmp.open("w", encoding="utf-8") as handle:
                for record in records:
                    handle.write(json.dumps(record) + "\n")
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(tmp, self.path)

    def size(self) -> int:
        return len(self.read_all())


class Sender:
    def __init__(
        self,
        collector_url: str,
        host: str,
        api_key: str | None,
        spooler: Spooler,
        timeout: float = 10,
        session=None,
    ):
        self.collector_url = collector_url
        self.host = host
        self.api_key = api_key
        self.spooler = spooler
        self.timeout = timeout
        self.session = session or requests.Session()

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}

        if self.api_key:
            headers["X-API-Key"] = self.api_key

        return headers

    def post(self, log_type: str, lines: list[str]) -> bool:
        """Attempt one delivery. Returns True when the collector handled it."""
        payload = {"host": self.host, "log_type": log_type, "lines": lines}

        try:
            response = self.session.post(
                self.collector_url,
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException:
            return False

        # 4xx means the batch itself is bad (e.g. unsupported log_type);
        # retrying it forever would only grow the spool, so treat it as done.
        return response.status_code < 500

    def send(self, log_type: str, lines: list[str]) -> bool:
        if not lines:
            return True

        if self.post(log_type, lines):
            return True

        self.spooler.enqueue(
            {
                "host": self.host,
                "log_type": log_type,
                "lines": lines,
                "created": time.time(),
            }
        )

        return False

    def drain_spool(self) -> bool:
        """Replay the spool FIFO. Returns True when it is empty."""
        records = self.spooler.read_all()

        if not records:
            return True

        remaining: list[dict] = []
        delivering = True

        for record in records:
            if delivering and self.post(
                record.get("log_type"), record.get("lines") or []
            ):
                continue

            delivering = False
            remaining.append(record)

        self.spooler.rewrite(remaining)

        return not remaining


def spool_worker(
    sender: Sender,
    stop_event: threading.Event,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    idle_delay: float = 2.0,
) -> None:
    delay = base_delay

    while not stop_event.is_set():
        if sender.drain_spool():
            delay = base_delay
            stop_event.wait(idle_delay)
        else:
            stop_event.wait(delay)
            delay = min(delay * 2, max_delay)


class Batcher:
    """Groups lines per log_type and flushes on size or time."""

    def __init__(
        self,
        sender: Sender,
        max_lines: int,
        max_seconds: float,
    ):
        self.sender = sender
        self.max_lines = max_lines
        self.max_seconds = max_seconds
        self._buffers: dict[str, list[str]] = defaultdict(list)
        self._lock = threading.Lock()

    def add(self, log_type: str, line: str) -> None:
        batch = None

        with self._lock:
            buffer = self._buffers[log_type]
            buffer.append(line)

            if len(buffer) >= self.max_lines:
                batch = self._buffers.pop(log_type)

        if batch:
            self.sender.send(log_type, batch)

    def flush(self) -> None:
        with self._lock:
            pending = list(self._buffers)
            batches = {log_type: self._buffers.pop(log_type) for log_type in pending}

        for log_type, lines in batches.items():
            self.sender.send(log_type, lines)

    def worker(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            stop_event.wait(self.max_seconds)
            self.flush()
