"""Response-action execution endpoints (task 4.7).

Recording a response action (``POST /api/incidents/{id}/actions``) only writes
it down.  Blocking the target IP is a separate, explicitly confirmed step:

    POST /api/actions/{id}/execute   # add the IP to the firewall blocklist
    POST /api/actions/{id}/unblock   # remove it again

Both require the ``lead``/``admin`` role, an explicit ``confirm: true`` and a
``block IP`` action whose target is a bare IPv4 address that is not
allow-listed.  Every execution is written to the audit log.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import ips
from ..database import get_db
from ..dependencies import require_role
from ..models.action import Action
from ..models.audit_log import AuditLog
from ..schemas.action import ActionExecutionRequest, ActionUnblockRequest


router = APIRouter(
    prefix="/api",
    tags=["Response Actions"],
)


def serialize_action(action: Action) -> dict:
    return {
        "id": action.id,
        "incident_id": action.incident_id,
        "action_type": action.action_type,
        "target": action.target,
        "performed_by": action.performed_by,
        "performed_at": action.performed_at,
        "reason": action.reason,
        "result": action.result,
        "status": action.status,
        "executed_at": action.executed_at,
    }


def _load_action(db: Session, action_id: int) -> Action:
    action = db.query(Action).filter(Action.id == action_id).first()

    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    return action


def _require_block_action(action: Action) -> None:
    if not ips.is_block_action(action.action_type):
        raise HTTPException(
            status_code=400,
            detail=(
                "Only 'block IP' actions can be executed via the IPS helper "
                f"(got '{action.action_type}')"
            ),
        )


def _require_confirmation(confirm: bool) -> None:
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Explicit human confirmation (confirm=true) is required",
        )


@router.post("/actions/{action_id}/execute")
def execute_action(
    action_id: int,
    payload: ActionExecutionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("lead", "admin")),
):
    """Run the block helper for a recorded response action."""
    action = _load_action(db, action_id)
    _require_block_action(action)
    _require_confirmation(payload.confirm)

    target = (action.target or "").strip()

    if not ips.is_valid_ipv4(target):
        raise HTTPException(
            status_code=400,
            detail=f"Action target is not a valid IPv4 address: '{target}'",
        )

    if ips.is_allowlisted(target):
        raise HTTPException(
            status_code=403,
            detail=f"{target} is allow-listed and cannot be blocked",
        )

    result = ips.block_ip(target, payload.timeout_seconds)

    action.status = "executed" if result.ok else "failed"
    action.executed_at = datetime.now(timezone.utc)
    action.result = result.message

    audit = AuditLog(
        user_id=current_user.id,
        action="response_action_executed",
        resource_type="action",
        resource_id=str(action.id),
        details=(
            f"Executed '{action.action_type}' on {target}: {result.message}"
            + (f" (reason: {payload.reason})" if payload.reason else "")
        ),
        created_at=datetime.now(timezone.utc),
    )

    db.add(audit)
    db.commit()
    db.refresh(action)

    return {
        "success": result.ok,
        "message": result.message,
        "action": serialize_action(action),
    }


@router.post("/actions/{action_id}/unblock")
def unblock_action(
    action_id: int,
    payload: ActionUnblockRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("lead", "admin")),
):
    """Remove a previously executed block."""
    action = _load_action(db, action_id)
    _require_block_action(action)
    _require_confirmation(payload.confirm)

    if action.status != "executed":
        raise HTTPException(
            status_code=400,
            detail=f"Action is not currently blocking (status={action.status})",
        )

    target = (action.target or "").strip()

    if not ips.is_valid_ipv4(target):
        raise HTTPException(
            status_code=400,
            detail=f"Action target is not a valid IPv4 address: '{target}'",
        )

    result = ips.unblock_ip(target)

    if result.ok:
        action.status = "unblocked"

    action.result = result.message

    audit = AuditLog(
        user_id=current_user.id,
        action="response_action_unblocked",
        resource_type="action",
        resource_id=str(action.id),
        details=(
            f"Unblocked {target}: {result.message}"
            + (f" (reason: {payload.reason})" if payload.reason else "")
        ),
        created_at=datetime.now(timezone.utc),
    )

    db.add(audit)
    db.commit()
    db.refresh(action)

    return {
        "success": result.ok,
        "message": result.message,
        "action": serialize_action(action),
    }
