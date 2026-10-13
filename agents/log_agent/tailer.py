"""Log sources: file tailing with rotation handling + a journald stream.

FileTailer (tasks 3.2, 3.3)
    Reads complete lines from a file, persisting ``(inode, offset)`` through an
    :class:`~agents.log_agent.offsets.OffsetStore`.  It copes with:

    * **restart** - resumes at the stored offset when the inode is unchanged,
      so nothing is re-sent and nothing is skipped;
    * **rotation** - the path now points at a new inode: the remaining bytes
      of the old file are drained first, then the new file is read from 0;
    * **truncation** - same inode but the file shrank: read again from 0.

JournalTailer (task 3.6)
    Wraps ``journalctl -f -o short-iso --cursor-file <file>`` for sources such
    as the kernel firewall log.  The journald cursor file *is* the offset.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time

from .offsets import OffsetStore


class FileTailer:
    def __init__(
        self,
        path: str,
        log_type: str,
        store: OffsetStore,
        poll_seconds: float = 1.0,
    ):
        self.path = path
        self.log_type = log_type
        self.store = store
        self.poll_seconds = poll_seconds

        self._fd = None
        self._inode: int | None = None
        self._offset = 0

    # -- lifecycle ------------------------------------------------------
    def close(self) -> None:
        if self._fd is not None:
            try:
                self._fd.close()
            finally:
                self._fd = None

    # -- reading --------------------------------------------------------
    def poll(self) -> list[str]:
        """Return any complete lines appended since the last call."""
        try:
            stat = os.stat(self.path)
        except FileNotFoundError:
            return []

        if self._fd is None:
            self._open_initial(stat)
        elif stat.st_ino != self._inode:
            # Rotation: drain what is left of the old file, then start the
            # new file from byte 0.
            drained = self._read_new()
            self.close()
            self._open_at(stat, 0)
            return drained + self._read_new()
        elif stat.st_size < self._offset:
            # Truncation: the file was emptied/reused in place.
            self.close()
            self._open_at(stat, 0)

        return self._read_new()

    # -- internals ------------------------------------------------------
    def _open_initial(self, stat) -> None:
        stored = self.store.get(self.path)

        # Resume only when the file is the same inode AND the stored offset is
        # still inside it.  A new inode (file recreated while we were down) or
        # a smaller file (in-place truncation / copytruncate rotation) means
        # the stream generations differ, so start again from byte 0.
        if (
            stored
            and stored.get("inode") == stat.st_ino
            and int(stored.get("offset", 0)) <= stat.st_size
        ):
            offset = int(stored.get("offset", 0))
        else:
            offset = 0

        self._open_at(stat, offset)

    def _open_at(self, stat, offset: int) -> None:
        try:
            fd = open(self.path, "rb")
        except FileNotFoundError:
            self._fd = None
            return

        fd.seek(offset)

        self._fd = fd
        self._inode = stat.st_ino
        self._offset = offset
        self.store.set(self.path, self._inode, self._offset)

    def _read_new(self) -> list[str]:
        if self._fd is None:
            return []

        self._fd.seek(self._offset)
        data = self._fd.read()

        if not data:
            return []

        # Never emit a trailing partial line: leave the offset pointing at its
        # first byte so it is completed and sent on the next poll.
        if not data.endswith(b"\n"):
            last_newline = data.rfind(b"\n")

            if last_newline == -1:
                return []

            data = data[: last_newline + 1]

        lines = [
            chunk.decode("utf-8", "replace")
            for chunk in data.split(b"\n")
            if chunk
        ]

        self._offset += len(data)
        self.store.set(self.path, self._inode, self._offset)

        return lines


class JournalTailer:
    def __init__(
        self,
        log_type: str,
        cursor_file: str,
        args: list[str] | None = None,
        command: str = "journalctl",
    ):
        self.log_type = log_type
        self.cursor_file = cursor_file
        self.args = list(args or ["-k"])
        self.command = command

    def build_command(self) -> list[str]:
        return [
            self.command,
            *self.args,
            "-f",
            "-o",
            "short-iso",
            "--cursor-file",
            self.cursor_file,
        ]

    def run(self, on_line, stop_event: threading.Event) -> None:
        """Stream journal lines to ``on_line`` until ``stop_event`` is set."""
        directory = os.path.dirname(self.cursor_file)
        if directory:
            os.makedirs(directory, exist_ok=True)

        process = subprocess.Popen(
            self.build_command(),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )

        try:
            if process.stdout is None:
                return

            for line in process.stdout:
                if stop_event.is_set():
                    break

                line = line.strip()

                if line:
                    on_line(line)
        finally:
            process.terminate()

            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def file_worker(
    tailer: FileTailer,
    on_line,
    stop_event: threading.Event,
) -> None:
    while not stop_event.is_set():
        try:
            for line in tailer.poll():
                on_line(tailer.log_type, line)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[agent] {tailer.path}: {exc}")

        stop_event.wait(tailer.poll_seconds)

    tailer.close()


def journal_worker(
    tailer: JournalTailer,
    on_line,
    stop_event: threading.Event,
) -> None:
    while not stop_event.is_set():
        try:
            tailer.run(
                lambda line: on_line(tailer.log_type, line),
                stop_event,
            )
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[agent] journal {tailer.log_type}: {exc}")

        if not stop_event.is_set():
            time.sleep(5)
