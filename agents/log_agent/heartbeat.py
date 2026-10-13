"""Periodic agent heartbeat + IDS service health (task 3.7).

Every ``heartbeat.seconds`` (default 30 s) the agent POSTs a heartbeat to the
backend at ``/api/agents/heartbeat``.  The payload reports the agent identity
and the current state of the IDS service so the dashboard's Overview can show
both the log agent and the IDS as healthy/unhealthy.
"""

from __future__ import annotations

import subprocess
import threading
import time

import requests


def ids_service_status(service: str, runner=subprocess.run) -> str:
    """Return ``active``/``inactive``/``failed``/``unknown`` for a unit."""
    try:
        result = runner(
            ["systemctl", "is-active", service],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"

    status = (result.stdout or "").strip()

    return status or "unknown"


class Heartbeat:
    def __init__(
        self,
        url: str,
        name: str,
        host: str,
        api_key: str | None,
        ids_service: str,
        seconds: int = 30,
        status_fn=ids_service_status,
        session=None,
    ):
        self.url = url
        self.name = name
        self.host = host
        self.api_key = api_key
        self.ids_service = ids_service
        self.seconds = seconds
        self.status_fn = status_fn
        self.session = session or requests.Session()

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}

        if self.api_key:
            headers["X-API-Key"] = self.api_key

        return headers

    def payload(self) -> dict:
        return {
            "name": self.name,
            "host": self.host,
            "status": "online",
            "ids": {
                "service": self.ids_service,
                "status": self.status_fn(self.ids_service),
            },
        }

    def beat(self) -> bool:
        try:
            response = self.session.post(
                self.url,
                headers=self._headers(),
                json=self.payload(),
                timeout=10,
            )
        except requests.RequestException:
            return False

        return response.status_code < 500

    def run(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            try:
                self.beat()
            except Exception as exc:  # pragma: no cover - defensive
                print(f"[agent] heartbeat error: {exc}")

            stop_event.wait(self.seconds)


def heartbeat_worker(heartbeat: Heartbeat, stop_event: threading.Event) -> None:
    heartbeat.run(stop_event)
