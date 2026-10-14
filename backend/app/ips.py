"""Response-action execution (task 4.7).

The Mini SOC IPS is deliberately *human-confirmed*: the backend never blocks on
its own.  An analyst records a "block IP" action, then confirms it in the
dashboard; this module runs the small ``soc-block`` helper through sudo to add
or remove the address in the nftables blocklist.

The helper path is configurable (``SOC_BLOCK_CMD``, default
``/usr/local/sbin/soc-block``) and its absence produces a clear failure rather
than a crash, so the platform stays usable on a host where the helper was not
installed.  The same allow-list the IDS suppresses is enforced here as well
(defence in depth): the helper refuses allow-listed addresses too.
"""

from __future__ import annotations

import ipaddress
import os
import shlex
import subprocess
from dataclasses import dataclass

from mini_soc_config import get_env, get_int, get_list

DEFAULT_HELPER = "/usr/local/sbin/soc-block"
DEFAULT_ALLOWLIST_FILE = "/etc/mini-soc/allowlist.txt"
DEFAULT_TIMEOUT = 3600
HELPER_TIMEOUT_SECONDS = 20

# Normalized forms of the contract's "block IP" action type.
BLOCK_ACTION_TYPES = {"block", "block_ip", "block ip", "block-ip"}


@dataclass
class HelperResult:
    ok: bool
    message: str
    returncode: int | None = None


def normalize_action_type(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_")


def is_block_action(value: str | None) -> bool:
    return normalize_action_type(value) in {
        "block",
        "block_ip",
        "block ip",
    }


def helper_path() -> str:
    return get_env("SOC_BLOCK_CMD", DEFAULT_HELPER)


def allowlist_file() -> str:
    return get_env("SOC_BLOCK_ALLOWLIST_FILE", DEFAULT_ALLOWLIST_FILE)


def use_sudo() -> bool:
    raw = str(get_env("SOC_BLOCK_USE_SUDO", "true")).lower()
    return raw not in {"0", "false", "no", "off"}


def default_timeout() -> int:
    return get_int("SOC_BLOCK_TIMEOUT", DEFAULT_TIMEOUT)


def is_valid_ipv4(value: str | None) -> bool:
    if not value:
        return False

    try:
        ipaddress.IPv4Address(value.strip())
    except ValueError:
        return False

    return True


def allowlisted_ips() -> set[str]:
    """Allow-listed addresses from the env and the helper's allow-list file."""
    ips = set(get_list("IDS_ALLOWLIST", []))

    path = allowlist_file()

    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()

                if line and not line.startswith("#"):
                    ips.add(line)
    except OSError:
        # No allow-list file is perfectly fine (nothing allow-listed).
        pass

    return ips


def is_allowlisted(value: str | None) -> bool:
    return bool(value) and value.strip() in allowlisted_ips()


def helper_command() -> list[str]:
    """Split ``SOC_BLOCK_CMD`` into argv.

    Normally the helper is a single absolute path, but allowing a command with
    arguments makes it easy to substitute a wrapper (and lets tests point it at
    ``python fake_helper.py``).
    """
    raw = helper_path()

    try:
        return shlex.split(raw, posix=(os.name != "nt"))
    except ValueError:
        return [raw]


def _command(args: list[str]) -> list[str]:
    command = [*helper_command(), *args]

    # Only escalate when we are not already root and sudo is enabled.
    if use_sudo() and hasattr(os, "geteuid") and os.geteuid() != 0:
        command = ["sudo", "-n", *command]

    return command


def _run(args: list[str]) -> HelperResult:
    command = _command(args)

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=HELPER_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        return HelperResult(
            ok=False,
            message=(
                f"block helper not found at {helper_path()} "
                "(set SOC_BLOCK_CMD or install deploy/soc-block)"
            ),
            returncode=None,
        )
    except subprocess.TimeoutExpired:
        return HelperResult(
            ok=False,
            message="block helper timed out",
            returncode=None,
        )
    except OSError as error:
        return HelperResult(ok=False, message=f"could not run helper: {error}")

    output = (completed.stdout or "").strip()
    error = (completed.stderr or "").strip()

    if completed.returncode != 0:
        return HelperResult(
            ok=False,
            message=error or output or f"helper exited {completed.returncode}",
            returncode=completed.returncode,
        )

    return HelperResult(
        ok=True,
        message=output or "ok",
        returncode=completed.returncode,
    )


def block_ip(ip: str, timeout: int | None = None) -> HelperResult:
    """Add ``ip`` to the firewall blocklist for ``timeout`` seconds."""
    ip = (ip or "").strip()

    if not is_valid_ipv4(ip):
        return HelperResult(ok=False, message=f"not a valid IPv4 address: {ip}")

    if is_allowlisted(ip):
        return HelperResult(ok=False, message=f"refusing allow-listed address {ip}")

    return _run(["add", ip, str(timeout or default_timeout())])


def unblock_ip(ip: str) -> HelperResult:
    """Remove ``ip`` from the firewall blocklist."""
    ip = (ip or "").strip()

    if not is_valid_ipv4(ip):
        return HelperResult(ok=False, message=f"not a valid IPv4 address: {ip}")

    return _run(["del", ip])
