"""Mini SOC log agent (Phase 3 rewrite).

Reads its configuration from ``/etc/mini-soc/agent.yaml`` and:

* tails the configured log files, remembering ``(inode, offset)`` in
  ``state.json`` so a restart never loses or duplicates a line (3.2);
* handles rotation and truncation by draining the old file then reading the
  new one from 0 (3.3);
* batches lines per source (N lines or T seconds) and sends **one** POST per
  batch to the collector (3.4);
* spools failed batches to disk and replays them FIFO with exponential
  backoff (3.5);
* streams the kernel firewall log via
  ``journalctl -k -f -o short-iso --cursor-file`` (3.6);
* sends a heartbeat (with IDS service status) every 30 s (3.7).

Run as a module so the repo root is importable::

    python -m agents.log_agent.agent
"""

from __future__ import annotations

import os
import signal
import threading

from .config import AgentConfig, load_config
from .heartbeat import Heartbeat, heartbeat_worker
from .offsets import OffsetStore
from .sender import Batcher, Sender, Spooler, spool_worker
from .tailer import FileTailer, JournalTailer, file_worker, journal_worker


def build_components(config: AgentConfig):
    """Construct the runtime objects (kept separate so tests can reuse them)."""
    os.makedirs(config.buffer_dir, exist_ok=True)
    os.makedirs(config.spool_dir, exist_ok=True)

    store = OffsetStore(config.state_file)
    spooler = Spooler(config.spool_file)
    sender = Sender(
        collector_url=config.collector_url,
        host=config.host,
        api_key=config.api_key,
        spooler=spooler,
    )
    batcher = Batcher(
        sender=sender,
        max_lines=config.batch_max_lines,
        max_seconds=config.batch_max_seconds,
    )
    heartbeat = Heartbeat(
        url=config.heartbeat_url,
        name=config.name,
        host=config.host,
        api_key=config.api_key,
        ids_service=config.ids_service,
        seconds=config.heartbeat_seconds,
    )

    return store, sender, batcher, heartbeat


def run(config: AgentConfig, stop_event: threading.Event | None = None) -> None:
    stop_event = stop_event or threading.Event()
    store, sender, batcher, heartbeat = build_components(config)

    def on_line(log_type: str, line: str) -> None:
        batcher.add(log_type, line)

    threads: list[threading.Thread] = []

    for source in config.files:
        tailer = FileTailer(
            path=source.path,
            log_type=source.log_type,
            store=store,
            poll_seconds=config.poll_seconds,
            multiline_start=source.multiline_start,
        )
        thread = threading.Thread(
            target=file_worker,
            args=(tailer, on_line, stop_event),
            name=f"file:{source.log_type}",
            daemon=True,
        )
        threads.append(thread)

    for source in config.journal:
        tailer = JournalTailer(
            log_type=source.log_type,
            cursor_file=source.cursor_file,
            args=source.args,
        )
        thread = threading.Thread(
            target=journal_worker,
            args=(tailer, on_line, stop_event),
            name=f"journal:{source.log_type}",
            daemon=True,
        )
        threads.append(thread)

    threads.append(
        threading.Thread(
            target=batcher.worker,
            args=(stop_event,),
            name="batcher",
            daemon=True,
        )
    )
    threads.append(
        threading.Thread(
            target=spool_worker,
            args=(sender, stop_event),
            name="spool",
            daemon=True,
        )
    )
    threads.append(
        threading.Thread(
            target=heartbeat_worker,
            args=(heartbeat, stop_event),
            name="heartbeat",
            daemon=True,
        )
    )

    for thread in threads:
        thread.start()

    stop_event.wait()

    # Final flush so lines buffered at shutdown are still delivered.
    batcher.flush()


def install_signal_handlers(stop_event: threading.Event) -> None:
    def handler(signum, frame):  # pragma: no cover - signal plumbing
        stop_event.set()

    for name in ("SIGTERM", "SIGINT"):
        sig = getattr(signal, name, None)
        if sig is not None:
            try:
                signal.signal(sig, handler)
            except ValueError:
                pass


def main() -> None:
    config = load_config()
    stop_event = threading.Event()
    install_signal_handlers(stop_event)

    print(
        f"[agent] starting as {config.name} -> {config.collector_url} "
        f"({len(config.files)} file sources, {len(config.journal)} journal sources)"
    )

    run(config, stop_event)


if __name__ == "__main__":
    main()
