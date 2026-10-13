"""Persistent read offsets keyed by ``(path, inode)`` (task 3.2).

The state file (``/var/lib/mini-soc/agent/state.json`` by default) maps a log
file path to the inode and byte offset the agent has consumed::

    {
      "/var/log/nginx/access.log": {"inode": 131074, "offset": 84213},
      "/var/log/auth.log":         {"inode": 131075, "offset": 1024}
    }

Storing the inode alongside the offset means a restart resumes exactly where
it left off (same inode) and a rotated/recreated file (new inode) is treated
as a brand new stream instead of replaying stale bytes.

Writes are atomic (write to a temp file in the same directory, then
``os.replace``) so a crash mid-write can never corrupt the state file.
"""

from __future__ import annotations

import json
import os
import threading
import tempfile
from pathlib import Path


class OffsetStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._state = self._load()

    def _load(self) -> dict:
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (FileNotFoundError, ValueError, OSError):
            return {}

        return data if isinstance(data, dict) else {}

    def get(self, key: str) -> dict | None:
        with self._lock:
            entry = self._state.get(key)
            return dict(entry) if isinstance(entry, dict) else None

    def set(self, key: str, inode: int, offset: int) -> None:
        with self._lock:
            self._state[key] = {"inode": int(inode), "offset": int(offset)}
            self._save_locked()

    def remove(self, key: str) -> None:
        with self._lock:
            self._state.pop(key, None)
            self._save_locked()

    def as_dict(self) -> dict:
        with self._lock:
            return {key: dict(value) for key, value in self._state.items()}

    def _save_locked(self) -> None:
        directory = self.path.parent
        directory.mkdir(parents=True, exist_ok=True)

        fd, tmp_name = tempfile.mkstemp(
            dir=str(directory),
            prefix=self.path.name + ".",
            suffix=".tmp",
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self._state, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(tmp_name, self.path)
        except OSError:
            try:
                os.remove(tmp_name)
            except OSError:
                pass
            raise
