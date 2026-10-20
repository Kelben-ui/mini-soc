"""Unit tests for the log agent (task 3.9).

Covers the three behaviours the phase calls out explicitly:
  * offsets persist across a restart (0 lines lost, 0 duplicated) - 3.2;
  * rotation and truncation are handled without losing a line - 3.3;
  * the disk spool keeps lines and replays them FIFO with backoff - 3.5.

Plus batching (3.4), config loading (3.1) and the journal command (3.6).
"""

import json
import os

import pytest
import requests

from agents.log_agent.config import load_config
from agents.log_agent.heartbeat import Heartbeat
from agents.log_agent.offsets import OffsetStore
from agents.log_agent.sender import Batcher, Sender, Spooler
from agents.log_agent.tailer import FileTailer, JournalTailer


# --------------------------------------------------------------------------- #
# Config (task 3.1)
# --------------------------------------------------------------------------- #
def _write_config(tmp_path, **overrides):
    body = {
        "collector_url": "http://collector:9000/ingest",
        "host": "host-a",
        "name": "agent-a",
        "heartbeat": {"url": "http://backend/api/agents/heartbeat", "seconds": 15},
        "batch": {"max_lines": 5, "max_seconds": 1},
        "buffer_dir": str(tmp_path / "buffer"),
        "files": [{"path": "/var/log/auth.log", "log_type": "auth"}],
        "journal": [
            {
                "log_type": "firewall",
                "args": ["-k"],
                "cursor_file": str(tmp_path / "k.cursor"),
            }
        ],
    }
    body.update(overrides)

    path = tmp_path / "agent.yaml"
    path.write_text(json.dumps(body), encoding="utf-8")

    return str(path)


def _clean_env(monkeypatch):
    """Isolate config loading from any ambient/.env-provided variables."""
    for name in (
        "AGENT_CONFIG",
        "SOC_HOSTNAME",
        "COLLECTOR_URL",
        "COLLECTOR_INGEST_URL",
        "BACKEND_URL",
        "VAR_DIR",
        "AGENT_BUFFER_DIR",
        "AGENT_HEARTBEAT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)


def test_config_loads_from_yaml(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    path = _write_config(tmp_path)

    config = load_config(path)

    assert config.collector_url == "http://collector:9000/ingest"
    assert config.name == "agent-a"
    assert config.host == "host-a"
    assert config.heartbeat_seconds == 15
    assert config.batch_max_lines == 5
    assert config.batch_max_seconds == 1
    assert config.state_file == str(tmp_path / "buffer" / "state.json")
    assert config.spool_file == str(
        tmp_path / "buffer" / "spool" / "batches.jsonl"
    )
    assert [(f.path, f.log_type) for f in config.files] == [
        ("/var/log/auth.log", "auth")
    ]
    assert config.journal[0].log_type == "firewall"


def test_config_env_overrides_api_key(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    path = _write_config(tmp_path)
    monkeypatch.setenv("INGEST_API_KEY", "secret-key")

    assert load_config(path).api_key == "secret-key"


def test_config_parses_multiline_start(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    path = _write_config(
        tmp_path,
        files=[
            {
                "path": "/var/log/nginx/error.log",
                "log_type": "nginx_error",
                "multiline_start": r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[",
            }
        ],
    )

    source = load_config(path).files[0]

    assert source.log_type == "nginx_error"
    assert source.multiline_start == r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \["


def test_config_multiline_start_defaults_to_none(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    path = _write_config(tmp_path)

    assert load_config(path).files[0].multiline_start is None


def test_config_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/agent.yaml")


# --------------------------------------------------------------------------- #
# Offsets (task 3.2)
# --------------------------------------------------------------------------- #
def test_offset_store_persists(tmp_path):
    state = tmp_path / "state.json"

    store = OffsetStore(str(state))
    store.set("/var/log/auth.log", 42, 128)

    reloaded = OffsetStore(str(state))
    assert reloaded.get("/var/log/auth.log") == {"inode": 42, "offset": 128}

    # The on-disk form must be valid JSON.
    assert json.loads(state.read_text(encoding="utf-8"))["/var/log/auth.log"] == {
        "inode": 42,
        "offset": 128,
    }


# --------------------------------------------------------------------------- #
# File tailer: offsets + rotation + truncation (tasks 3.2, 3.3)
# --------------------------------------------------------------------------- #
def test_tailer_reads_complete_lines_only(tmp_path):
    log = tmp_path / "auth.log"
    log.write_bytes(b"first\nsec")

    tailer = FileTailer(str(log), "auth", OffsetStore(str(tmp_path / "s.json")))

    assert tailer.poll() == ["first"]  # partial "sec" withheld

    with log.open("ab") as handle:
        handle.write(b"ond\n")

    assert tailer.poll() == ["second"]


def test_restart_loses_and_duplicates_nothing(tmp_path):
    log = tmp_path / "auth.log"
    state = tmp_path / "state.json"
    log.write_bytes(b"a\nb\nc\n")

    tailer = FileTailer(str(log), "auth", OffsetStore(str(state)))
    assert tailer.poll() == ["a", "b", "c"]

    # Simulate a restart: brand new store + tailer over the same files.
    restarted = FileTailer(str(log), "auth", OffsetStore(str(state)))
    assert restarted.poll() == []

    with log.open("ab") as handle:
        handle.write(b"d\n")

    assert restarted.poll() == ["d"]


def test_restart_after_inplace_truncate_reads_new_stream(tmp_path):
    log = tmp_path / "auth.log"
    state = tmp_path / "state.json"
    log.write_bytes(b"a\nb\nc\n")

    tailer = FileTailer(str(log), "auth", OffsetStore(str(state)))
    assert tailer.poll() == ["a", "b", "c"]

    # Truncated and rewritten in place (same inode) while the agent was down.
    log.write_bytes(b"x\n")

    restarted = FileTailer(str(log), "auth", OffsetStore(str(state)))
    assert restarted.poll() == ["x"]


def test_truncation_replays_from_start(tmp_path):
    log = tmp_path / "auth.log"
    log.write_bytes(b"one\ntwo\nthree\n")

    tailer = FileTailer(str(log), "auth", OffsetStore(str(tmp_path / "s.json")))
    assert tailer.poll() == ["one", "two", "three"]

    # Same inode, smaller file -> truncation.
    log.write_bytes(b"fresh\n")

    assert tailer.poll() == ["fresh"]


@pytest.mark.skipif(
    os.name == "nt",
    reason="Windows cannot rename a file while the agent holds it open; "
    "the POSIX logrotate path is exercised in CI (Linux) and on EC2",
)
def test_rotation_drains_old_then_reads_new(tmp_path):
    log = tmp_path / "auth.log"
    log.write_bytes(b"a\n")

    tailer = FileTailer(str(log), "auth", OffsetStore(str(tmp_path / "s.json")))
    assert tailer.poll() == ["a"]

    # A line lands in the old inode, then logrotate renames it away and a new
    # file takes its place.
    with log.open("ab") as handle:
        handle.write(b"b\n")

    rotated = tmp_path / "auth.log.1"
    os.replace(log, rotated)
    log.write_bytes(b"c\n")

    assert tailer.poll() == ["b", "c"]
    assert tailer.poll() == []


# --------------------------------------------------------------------------- #
# Multi-line join (nginx error log: PHP FastCGI stack traces)
# --------------------------------------------------------------------------- #
NGINX_START = r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \["

HEADER = (
    '2026/10/20 10:56:10 [error] 1769#1769: *19 FastCGI sent in stderr: '
    '"PHP message: PHP Warning:  include(../../etc/passwd): Failed to open '
    'stream: No such file or directory in /var/www/dvwa/login.php on line 8'
)
CONTINUATION = [
    "Stack trace:",
    "#0 /var/www/dvwa/login.php(8): dvwaDatabaseConnect()",
    "#1 {main}",
    '  thrown in /var/www/dvwa/dvwa/includes/dvwaPage.inc.php on line 569" '
    "while reading response header from upstream, client: 127.0.0.1",
]
SECOND = (
    '2026/10/20 10:57:00 [error] 1770#1770: *20 open() "/nope" failed '
    "(2: No such file or directory)"
)


def test_multiline_join_folds_continuation_lines(tmp_path):
    log = tmp_path / "error.log"
    body = "\n".join([HEADER, *CONTINUATION, SECOND]) + "\n"
    log.write_bytes(body.encode())

    tailer = FileTailer(
        str(log),
        "nginx_error",
        OffsetStore(str(tmp_path / "s.json")),
        multiline_start=NGINX_START,
    )

    # Both headers were read in one poll: the first entry (header + 4
    # continuation lines) is complete and released; the second is held pending.
    assert tailer.poll() == ["\n".join([HEADER, *CONTINUATION])]
    # An idle poll releases the trailing entry.
    assert tailer.poll() == [SECOND]


def test_multiline_without_flag_is_unchanged(tmp_path):
    log = tmp_path / "error.log"
    log.write_bytes(("\n".join([HEADER, *CONTINUATION]) + "\n").encode())

    tailer = FileTailer(
        str(log), "nginx_error", OffsetStore(str(tmp_path / "s.json"))
    )

    # Default behaviour: every physical line is emitted separately.
    assert tailer.poll() == [HEADER, *CONTINUATION]


def test_multiline_entry_split_across_polls_is_assembled(tmp_path):
    log = tmp_path / "error.log"
    log.write_bytes((HEADER + "\n").encode())

    tailer = FileTailer(
        str(log),
        "nginx_error",
        OffsetStore(str(tmp_path / "s.json")),
        multiline_start=NGINX_START,
    )

    # Header alone: bytes were read, so the entry may still be growing - held.
    assert tailer.poll() == []

    # A later poll reads the continuation lines: still held.
    with log.open("ab") as handle:
        handle.write(("\n".join(CONTINUATION) + "\n").encode())

    assert tailer.poll() == []

    # An idle poll (no new bytes) proves the entry complete and releases it,
    # with the continuation lines folded in.
    assert tailer.poll() == ["\n".join([HEADER, *CONTINUATION])]


def test_multiline_idle_flush_releases_trailing_entry(tmp_path):
    log = tmp_path / "error.log"
    log.write_bytes((HEADER + "\n").encode())

    tailer = FileTailer(
        str(log),
        "nginx_error",
        OffsetStore(str(tmp_path / "s.json")),
        multiline_start=NGINX_START,
    )

    assert tailer.poll() == []   # header read, entry held
    assert tailer.poll() == [HEADER]  # idle poll releases it
    assert tailer.poll() == []   # no duplicate


def test_multiline_flush_pending_emits_trailing_entry(tmp_path):
    log = tmp_path / "error.log"
    log.write_bytes((HEADER + "\n").encode())

    tailer = FileTailer(
        str(log),
        "nginx_error",
        OffsetStore(str(tmp_path / "s.json")),
        multiline_start=NGINX_START,
    )

    assert tailer.poll() == []
    assert tailer.flush_pending() == [HEADER]
    # Flushing twice must not duplicate the entry.
    assert tailer.flush_pending() == []


@pytest.mark.skipif(
    os.name == "nt",
    reason="Windows cannot rename a file while the agent holds it open",
)
def test_multiline_rotation_does_not_merge_across_files(tmp_path):
    log = tmp_path / "error.log"
    log.write_bytes((HEADER + "\n").encode())

    tailer = FileTailer(
        str(log),
        "nginx_error",
        OffsetStore(str(tmp_path / "s.json")),
        multiline_start=NGINX_START,
    )
    assert tailer.poll() == []  # header held pending

    rotated = tmp_path / "error.log.1"
    os.replace(log, rotated)
    log.write_bytes((SECOND + "\n").encode())

    # The old file's pending entry is emitted before the new file's first line,
    # and the new file's first line is now the held entry.
    assert tailer.poll() == [HEADER]
    assert tailer.poll() == [SECOND]


# --------------------------------------------------------------------------- #
# Spool + FIFO + backoff (task 3.5)
# --------------------------------------------------------------------------- #
class _Response:
    def __init__(self, status_code):
        self.status_code = status_code


class _Session:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append(json)
        outcome = self.outcomes.pop(0)

        if isinstance(outcome, Exception):
            raise outcome

        return _Response(outcome)


def _sender(tmp_path, outcomes):
    spooler = Spooler(str(tmp_path / "spool.jsonl"))
    session = _Session(outcomes)

    return (
        Sender(
            collector_url="http://collector/ingest",
            host="host-a",
            api_key="k",
            spooler=spooler,
            session=session,
        ),
        spooler,
        session,
    )


def test_send_spools_on_failure_and_replays(tmp_path):
    sender, spooler, _ = _sender(tmp_path, [requests.ConnectionError("down")])

    assert sender.send("auth", ["line-1"]) is False
    assert spooler.size() == 1

    sender.session.outcomes.append(201)
    assert sender.drain_spool() is True
    assert spooler.size() == 0


def test_spool_is_fifo_and_stops_at_first_failure(tmp_path):
    sender, spooler, session = _sender(
        tmp_path, [requests.ConnectionError("x"), requests.ConnectionError("y")]
    )

    sender.send("auth", ["one"])
    sender.send("auth", ["two"])
    assert spooler.size() == 2

    # First replay still failing: nothing after it must be attempted.
    session.outcomes.extend([500, 201])
    assert sender.drain_spool() is False
    assert spooler.size() == 2
    assert [call["lines"] for call in session.calls[-1:]] == [["one"]]

    # Collector recovers: FIFO order preserved.
    session.outcomes.extend([201, 201])
    assert sender.drain_spool() is True
    assert spooler.size() == 0

    delivered = [call["lines"] for call in session.calls if call["lines"]]
    assert delivered[-2:] == [["one"], ["two"]]


def test_client_error_is_not_spooled(tmp_path):
    sender, spooler, _ = _sender(tmp_path, [400])

    assert sender.send("auth", ["bad"]) is True
    assert spooler.size() == 0


# --------------------------------------------------------------------------- #
# Batching (task 3.4)
# --------------------------------------------------------------------------- #
class _RecordingSender:
    def __init__(self):
        self.batches = []

    def send(self, log_type, lines):
        self.batches.append((log_type, list(lines)))
        return True


def test_batcher_flushes_on_size():
    sender = _RecordingSender()
    batcher = Batcher(sender, max_lines=3, max_seconds=60)

    batcher.add("auth", "a")
    batcher.add("auth", "b")
    assert sender.batches == []

    batcher.add("auth", "c")
    assert sender.batches == [("auth", ["a", "b", "c"])]


def test_batcher_flushes_on_time():
    sender = _RecordingSender()
    batcher = Batcher(sender, max_lines=100, max_seconds=60)

    batcher.add("nginx_error", "x")
    batcher.add("auth", "y")
    batcher.flush()

    assert sorted(sender.batches) == [("auth", ["y"]), ("nginx_error", ["x"])]


# --------------------------------------------------------------------------- #
# Journal command (task 3.6)
# --------------------------------------------------------------------------- #
def test_journal_command_uses_short_iso_and_cursor_file():
    tailer = JournalTailer(
        log_type="firewall",
        cursor_file="/var/lib/mini-soc/agent/journal-kernel.cursor",
        args=["-k"],
    )

    command = tailer.build_command()

    assert command[0] == "journalctl"
    assert "-k" in command
    assert "-f" in command
    assert command[command.index("-o") + 1] == "short-iso"
    assert command[command.index("--cursor-file") + 1].endswith(".cursor")


# --------------------------------------------------------------------------- #
# Heartbeat (task 3.7)
# --------------------------------------------------------------------------- #
def test_heartbeat_reports_ids_status():
    session = _Session([200])
    heartbeat = Heartbeat(
        url="http://backend/api/agents/heartbeat",
        name="agent-a",
        host="host-a",
        api_key="k",
        ids_service="mini-soc-ids",
        status_fn=lambda service: "active",
        session=session,
    )

    assert heartbeat.beat() is True
    assert session.calls[0]["ids"] == {
        "service": "mini-soc-ids",
        "status": "active",
    }
