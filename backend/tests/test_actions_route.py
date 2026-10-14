"""Backend response-action execution (task 4.7).

Calls the route functions directly (the venv's starlette wants ``httpx2`` and
``TestClient`` is unavailable).  ``SOC_BLOCK_CMD`` points at a throwaway Python
script that records its argv, so the real ``soc-block``/sudo path is exercised
without touching a firewall.
"""

import sys
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from backend.app import ips
from backend.app.models.action import Action
from backend.app.models.audit_log import AuditLog
from backend.app.models.incident import Incident
from backend.app.models.user import User
from backend.app.routers.actions import execute_action, unblock_action
from backend.app.schemas.action import ActionExecutionRequest, ActionUnblockRequest


FAKE_HELPER = """\
import os
import sys

log = os.environ.get("SOC_BLOCK_FAKE_LOG")
if log:
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(" ".join(sys.argv[1:]) + "\\n")

sys.exit(int(os.environ.get("SOC_BLOCK_FAKE_EXIT", "0")))
"""


@pytest.fixture()
def helper(tmp_path, monkeypatch):
    """Point SOC_BLOCK_CMD at a fake helper and record what it was asked."""
    script = tmp_path / "fake_helper.py"
    script.write_text(FAKE_HELPER, encoding="utf-8")

    log = tmp_path / "helper.log"

    monkeypatch.setenv("SOC_BLOCK_CMD", f"{sys.executable} {script}")
    monkeypatch.setenv("SOC_BLOCK_USE_SUDO", "false")
    monkeypatch.setenv("SOC_BLOCK_FAKE_LOG", str(log))
    monkeypatch.setenv("SOC_BLOCK_ALLOWLIST_FILE", str(tmp_path / "allowlist.txt"))
    monkeypatch.delenv("IDS_ALLOWLIST", raising=False)

    def calls():
        try:
            return log.read_text(encoding="utf-8").split()
        except FileNotFoundError:
            return []

    return calls


def make_user(db, role="lead"):
    user = User(
        username=f"user-{role}-{uuid.uuid4().hex[:12]}",
        password_hash="x",
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_incident(db):
    incident = Incident(
        incident_code=f"INC-{uuid.uuid4().hex[:10]}",
        title="Test incident",
        severity="high",
        status="open",
        created_at=datetime.now(timezone.utc),
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


def make_action(db, incident, user, action_type="block ip", target="203.0.113.50"):
    action = Action(
        incident_id=incident.incident_id,
        action_type=action_type,
        target=target,
        performed_by=user.id,
        performed_at=datetime.now(timezone.utc),
        reason="confirmed malicious source",
        result="pending",
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


def test_execute_block_runs_helper_and_marks_executed(db, helper, monkeypatch):
    lead = make_user(db)
    incident = make_incident(db)
    action = make_action(db, incident, lead)

    result = execute_action(
        action.id,
        ActionExecutionRequest(confirm=True, reason="confirmed"),
        db=db,
        current_user=lead,
    )

    assert result["success"] is True
    assert result["action"]["status"] == "executed"
    assert result["action"]["executed_at"] is not None

    calls = helper()
    assert calls[:2] == ["add", "203.0.113.50"]

    audit = (
        db.query(AuditLog)
        .filter(AuditLog.action == "response_action_executed")
        .first()
    )
    assert audit is not None


def test_execute_requires_confirmation(db, helper):
    lead = make_user(db)
    incident = make_incident(db)
    action = make_action(db, incident, lead, target="203.0.113.51")

    with pytest.raises(HTTPException) as error:
        execute_action(
            action.id,
            ActionExecutionRequest(confirm=False),
            db=db,
            current_user=lead,
        )

    assert error.value.status_code == 400
    assert helper() == []


def test_execute_rejects_non_block_action(db, helper):
    lead = make_user(db)
    incident = make_incident(db)
    action = make_action(db, incident, lead, action_type="reset password")

    with pytest.raises(HTTPException) as error:
        execute_action(
            action.id,
            ActionExecutionRequest(confirm=True),
            db=db,
            current_user=lead,
        )

    assert error.value.status_code == 400
    assert helper() == []


def test_execute_rejects_invalid_target(db, helper):
    lead = make_user(db)
    incident = make_incident(db)
    action = make_action(db, incident, lead, target="not-an-ip")

    with pytest.raises(HTTPException) as error:
        execute_action(
            action.id,
            ActionExecutionRequest(confirm=True),
            db=db,
            current_user=lead,
        )

    assert error.value.status_code == 400
    assert helper() == []


def test_execute_rejects_allowlisted_target(db, helper, tmp_path):
    lead = make_user(db)
    incident = make_incident(db)
    action = make_action(db, incident, lead, target="203.0.113.77")

    allowlist = tmp_path / "allowlist.txt"
    allowlist.write_text("203.0.113.77\n", encoding="utf-8")

    with pytest.raises(HTTPException) as error:
        execute_action(
            action.id,
            ActionExecutionRequest(confirm=True),
            db=db,
            current_user=lead,
        )

    assert error.value.status_code == 403
    assert helper() == []


def test_execute_reports_missing_helper(db, tmp_path, monkeypatch):
    monkeypatch.setenv("SOC_BLOCK_CMD", str(tmp_path / "does-not-exist"))
    monkeypatch.setenv("SOC_BLOCK_USE_SUDO", "false")
    monkeypatch.delenv("IDS_ALLOWLIST", raising=False)

    lead = make_user(db)
    incident = make_incident(db)
    action = make_action(db, incident, lead, target="203.0.113.88")

    result = execute_action(
        action.id,
        ActionExecutionRequest(confirm=True),
        db=db,
        current_user=lead,
    )

    assert result["success"] is False
    assert result["action"]["status"] == "failed"
    assert "not found" in result["message"]


def test_unblock_after_execute(db, helper):
    lead = make_user(db)
    incident = make_incident(db)
    action = make_action(db, incident, lead, target="203.0.113.99")

    execute_action(
        action.id,
        ActionExecutionRequest(confirm=True),
        db=db,
        current_user=lead,
    )

    result = unblock_action(
        action.id,
        ActionUnblockRequest(confirm=True),
        db=db,
        current_user=lead,
    )

    assert result["success"] is True
    assert result["action"]["status"] == "unblocked"

    calls = helper()
    assert calls[3:5] == ["del", "203.0.113.99"]


def test_unblock_requires_an_executed_block(db, helper):
    lead = make_user(db)
    incident = make_incident(db)
    action = make_action(db, incident, lead, target="203.0.113.100")

    with pytest.raises(HTTPException) as error:
        unblock_action(
            action.id,
            ActionUnblockRequest(confirm=True),
            db=db,
            current_user=lead,
        )

    assert error.value.status_code == 400
    assert helper() == []


# --- unit tests for the helper wrapper --------------------------------------


def test_is_valid_ipv4():
    assert ips.is_valid_ipv4("203.0.113.5")
    assert not ips.is_valid_ipv4("203.0.113.999")
    assert not ips.is_valid_ipv4("203.0.113.0/24")
    assert not ips.is_valid_ipv4("example.com")
    assert not ips.is_valid_ipv4("")


def test_is_block_action_normalizes():
    assert ips.is_block_action("block IP")
    assert ips.is_block_action("block_ip")
    assert ips.is_block_action("Block-IP")
    assert not ips.is_block_action("isolate host")
    assert not ips.is_block_action(None)


def test_default_helper_path(monkeypatch):
    monkeypatch.delenv("SOC_BLOCK_CMD", raising=False)
    assert ips.helper_path() == "/usr/local/sbin/soc-block"
