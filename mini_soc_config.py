"""Centralized runtime configuration for every Mini SOC service.

All services share one configuration file.  The resolution order is:

1. ``$ENV_FILE`` when set (explicit override).
2. ``/etc/mini-soc/.env`` (production; systemd also injects it via
   ``EnvironmentFile=``).
3. ``<repo>/.env`` (local development fallback).

Loading is best-effort and never overrides a value that already exists in
the process environment (``override=False``), so systemd-provided variables
always win over the file.  Importing this module is enough to make the
environment available; call the ``get_*`` helpers instead of reading
``os.environ`` directly so defaults stay in one place.
"""

from __future__ import annotations

import os
from pathlib import Path

try:  # python-dotenv is a pinned dependency, but stay importable without it
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover

    def load_dotenv(*_args, **_kwargs):  # type: ignore[misc]
        return False


# <repo>/mini_soc_config.py -> <repo>
REPO_ROOT = Path(__file__).resolve().parent
SYSTEM_ENV_FILE = Path("/etc/mini-soc/.env")


def resolve_env_file() -> Path | None:
    """Return the env file to load, or ``None`` when none exists."""
    explicit = os.getenv("ENV_FILE")
    if explicit:
        return Path(explicit)
    if SYSTEM_ENV_FILE.exists():
        return SYSTEM_ENV_FILE
    repo_env = REPO_ROOT / ".env"
    if repo_env.exists():
        return repo_env
    return None


ENV_FILE = resolve_env_file()

if ENV_FILE is not None:
    load_dotenv(ENV_FILE, override=False)


def get_env(name: str, default=None):
    """Return a non-empty environment variable or ``default``."""
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def get_int(name: str, default: int) -> int:
    try:
        return int(get_env(name, default))
    except (TypeError, ValueError):
        return default


def get_float(name: str, default: float) -> float:
    try:
        return float(get_env(name, default))
    except (TypeError, ValueError):
        return default


def get_list(name: str, default=None) -> list[str]:
    raw = get_env(name)
    if not raw:
        return list(default) if default else []
    return [item.strip() for item in raw.split(",") if item.strip()]


def state_dir() -> Path:
    """Base state directory (/var/lib/mini-soc)."""
    return Path(get_env("VAR_DIR", "/var/lib/mini-soc"))


def evidence_dir() -> Path:
    return Path(get_env("EVIDENCE_DIR", str(state_dir() / "evidence")))


def rules_dir() -> Path:
    return Path(get_env("RULES_DIR", str(REPO_ROOT / "rules")))


def spool_dir() -> Path:
    return Path(get_env("AGENT_SPOOL_DIR", str(state_dir() / "agent" / "spool")))
