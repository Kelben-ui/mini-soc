"""Agent configuration loader (task 3.1).

The agent reads every runtime value from ``agent.yaml`` (installed at
``/etc/mini-soc/agent.yaml``).  A small set of environment overrides - the
systemd ``EnvironmentFile`` values - let the deployment point the agent at a
different file or URL without editing the YAML.

Nothing about the host, collector, watched files, batching or buffer
directory is hard-coded in the agent: if a source is not listed in the config
it is not tailed.
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = "/etc/mini-soc/agent.yaml"
DEFAULT_IDS_SERVICE = "mini-soc-ids"


@dataclass
class FileSource:
    """A log file the agent tails line by line.

    ``multiline_start`` (optional) is a regex that identifies the *first* line
    of a logical entry.  When set, physical lines that do not match it are
    continuation lines and are joined onto the entry they belong to
    (newline-separated) before being batched.  This keeps multi-line records -
    e.g. the PHP FastCGI stack traces nginx writes to ``error.log`` - intact so
    the collector parser sees one complete entry instead of orphaned
    continuation lines (which it cannot parse and would reject with HTTP 422).
    """

    path: str
    log_type: str
    multiline_start: str | None = None


@dataclass
class JournalSource:
    """A ``journalctl`` stream (e.g. the kernel firewall log)."""

    log_type: str
    args: list[str]
    cursor_file: str


@dataclass
class AgentConfig:
    collector_url: str
    api_key: str | None

    host: str
    name: str

    heartbeat_url: str
    heartbeat_seconds: int
    ids_service: str

    batch_max_lines: int
    batch_max_seconds: float
    poll_seconds: float

    buffer_dir: str
    state_file: str
    spool_dir: str
    spool_file: str

    files: list[FileSource] = field(default_factory=list)
    journal: list[JournalSource] = field(default_factory=list)


def _env(*names: str) -> str | None:
    """Return the first non-empty environment variable among ``names``."""
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _resolve_collector_url(raw: dict) -> str:
    url = raw.get("collector_url") or _env("COLLECTOR_INGEST_URL")
    if not url:
        base = _env("COLLECTOR_URL")
        url = f"{base.rstrip('/')}/ingest" if base else None
    if not url:
        raise ValueError(
            "collector_url is not configured (set it in agent.yaml or "
            "COLLECTOR_INGEST_URL/COLLECTOR_URL in the environment)"
        )
    return url


def _resolve_host(raw: dict) -> str:
    return (
        _env("SOC_HOSTNAME")
        or raw.get("host")
        or socket.gethostname()
    )


def _resolve_heartbeat(raw: dict) -> tuple[str, int, str]:
    heartbeat = raw.get("heartbeat") or {}

    url = heartbeat.get("url")
    if not url:
        base = _env("BACKEND_URL") or "http://127.0.0.1:8000"
        url = f"{base.rstrip('/')}/api/agents/heartbeat"

    seconds = int(heartbeat.get("seconds") or _env("AGENT_HEARTBEAT_SECONDS") or 30)

    service = heartbeat.get("ids_service") or DEFAULT_IDS_SERVICE

    return url, seconds, service


def _resolve_paths(raw: dict) -> tuple[str, str, str, str]:
    buffer_dir = (
        raw.get("buffer_dir")
        or _env("AGENT_BUFFER_DIR")
        or os.path.join(
            _env("VAR_DIR", "/var/lib/mini-soc"),
            "agent",
        )
    )

    state_file = raw.get("state_file") or os.path.join(buffer_dir, "state.json")

    spool_dir = raw.get("spool_dir") or os.path.join(buffer_dir, "spool")
    spool_file = raw.get("spool_file") or os.path.join(spool_dir, "batches.jsonl")

    return buffer_dir, state_file, spool_dir, spool_file


def _resolve_files(raw: dict) -> list[FileSource]:
    sources: list[FileSource] = []

    for entry in raw.get("files") or []:
        if isinstance(entry, str):
            raise ValueError(
                f"file source {entry!r} must be a mapping with "
                "'path' and 'log_type'"
            )

        path = entry.get("path")
        log_type = entry.get("log_type")

        if not path or not log_type:
            raise ValueError("every file source needs 'path' and 'log_type'")

        multiline_start = entry.get("multiline_start")

        sources.append(
            FileSource(
                path=path,
                log_type=log_type,
                multiline_start=multiline_start,
            )
        )

    return sources


def _resolve_journal(raw: dict) -> list[JournalSource]:
    sources: list[JournalSource] = []

    for entry in raw.get("journal") or []:
        log_type = entry.get("log_type")
        cursor_file = entry.get("cursor_file")

        if not log_type or not cursor_file:
            raise ValueError(
                "every journal source needs 'log_type' and 'cursor_file'"
            )

        args = entry.get("args") or ["-k"]

        sources.append(
            JournalSource(
                log_type=log_type,
                args=list(args),
                cursor_file=cursor_file,
            )
        )

    return sources


def load_config(path: str | None = None) -> AgentConfig:
    """Load and validate the agent configuration."""
    config_path = (
        path
        or _env("AGENT_CONFIG")
        or DEFAULT_CONFIG_PATH
    )

    resolved = Path(config_path)

    if not resolved.exists():
        raise FileNotFoundError(
            f"agent config not found: {config_path} "
            "(copy agents/agent.example.yaml to /etc/mini-soc/agent.yaml)"
        )

    with resolved.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    if not isinstance(raw, dict):
        raise ValueError(f"agent config {config_path} must be a YAML mapping")

    batch = raw.get("batch") or {}

    host = _resolve_host(raw)
    heartbeat_url, heartbeat_seconds, ids_service = _resolve_heartbeat(raw)
    buffer_dir, state_file, spool_dir, spool_file = _resolve_paths(raw)

    return AgentConfig(
        collector_url=_resolve_collector_url(raw),
        api_key=_env("INGEST_API_KEY") or raw.get("api_key"),
        host=host,
        name=raw.get("name") or host,
        heartbeat_url=heartbeat_url,
        heartbeat_seconds=heartbeat_seconds,
        ids_service=ids_service,
        batch_max_lines=int(batch.get("max_lines") or 200),
        batch_max_seconds=float(batch.get("max_seconds") or 2),
        poll_seconds=float(raw.get("poll_seconds") or 1),
        buffer_dir=buffer_dir,
        state_file=state_file,
        spool_dir=spool_dir,
        spool_file=spool_file,
        files=_resolve_files(raw),
        journal=_resolve_journal(raw),
    )
