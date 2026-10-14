from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from mini_soc_config import evidence_dir

from ..database import get_db
from ..dependencies import get_current_user, require_role
from ..models.alert import Alert
from ..models.alert_event import AlertEvent
from ..models.audit_log import AuditLog
from ..models.event import Event
from ..models.incident import Incident
from ..models.user import User
from ..schemas.alert import AlertUpdate

router = APIRouter(
    prefix="/api",
    tags=["Alerts"]
)


def _serialize_alert(alert):
    """The full alert payload shared by the list/detail endpoints."""
    return {
        "alert_id": alert.alert_id,
        "rule_id": alert.rule_id,
        "title": alert.title,
        "severity": alert.severity,
        "status": alert.status,
        "first_seen": alert.first_seen,
        "last_seen": alert.last_seen,
        "src_ip": alert.src_ip,
        "dst_ip": alert.dst_ip,
        "dst_host": alert.dst_host,
        "mitre": alert.mitre,
        "category": alert.category,
        "count": alert.count,
        "chain_id": alert.chain_id,
        "assigned_to": alert.assigned_to,
        "incident_id": alert.incident_id,
    }


@router.get("/alerts")
def get_alerts(
    severity: str | None = Query(default=None),
    status: str | None = Query(default=None),
    rule_id: str | None = Query(default=None),
    rule: str | None = Query(default=None),
    src_ip: str | None = Query(default=None),
    assigned_to: int | None = Query(default=None),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(require_role("analyst", "lead", "admin"))
):
    """List alerts with the filters required by the dashboard (spec §13.4)."""
    query = db.query(Alert)

    if severity:
        query = query.filter(func.upper(Alert.severity) == severity.upper())

    if status:
        query = query.filter(func.upper(Alert.status) == status.upper())

    rule_filter = rule_id or rule

    if rule_filter:
        query = query.filter(Alert.rule_id == rule_filter)

    if src_ip:
        query = query.filter(Alert.src_ip == src_ip)

    if assigned_to is not None:
        query = query.filter(Alert.assigned_to == assigned_to)

    if start_time:
        query = query.filter(Alert.last_seen >= start_time)

    if end_time:
        query = query.filter(Alert.last_seen <= end_time)

    total = query.count()

    alerts = (
        query.order_by(Alert.last_seen.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "items": [_serialize_alert(alert) for alert in alerts],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/alerts/{alert_id}")
def get_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("analyst", "lead", "admin"))
):
    alert = db.query(Alert).filter(
        Alert.alert_id == alert_id
    ).first()

    if not alert:
        raise HTTPException(
            status_code=404,
            detail="Alert not found"
        )

    events = (
        db.query(Event)
        .join(AlertEvent, AlertEvent.event_id == Event.event_id)
        .filter(AlertEvent.alert_id == alert_id)
        .order_by(Event.timestamp.asc())
        .all()
    )

    payload = _serialize_alert(alert)

    payload["events"] = [
        {
            "event_id": event.event_id,
            "timestamp": event.timestamp,
            "host": event.host,
            "log_type": event.log_type,
            "category": event.category,
            "action": event.action,
            "src_ip": event.src_ip,
            "dst_ip": event.dst_ip,
            "user": event.user,
            "outcome": event.outcome,
            "details": event.details,
            "raw": event.raw,
        }
        for event in events
    ]

    return payload

@router.patch("/alerts/{alert_id}")
def update_alert(
    alert_id: int,
    alert_data: AlertUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("lead", "admin"))
):
    alert = db.query(Alert).filter(
        Alert.alert_id == alert_id
    ).first()

    if not alert:
        raise HTTPException(
            status_code=404,
            detail="Alert not found"
        )

    # Validate assigned analyst if assignment is provided
    if alert_data.assigned_to is not None:
        user = db.query(User).filter(
            User.id == alert_data.assigned_to
        ).first()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="Assigned user not found"
            )

    # Validate status change
    if alert_data.status is not None:
        new_status = alert_data.status.upper()

        allowed_statuses = {
            "NEW",
            "INVESTIGATING",
            "CONTAINED",
            "RESOLVED",
            "FALSE POSITIVE",
        }

        if new_status not in allowed_statuses:
            raise HTTPException(
                status_code=400,
                detail="Invalid alert status"
            )

        current_status = alert.status.upper()

        # Existing model uses "open" as its default.
        if current_status == "OPEN":
            current_status = "NEW"

        allowed_transitions = {
            "NEW": {"INVESTIGATING", "FALSE POSITIVE"},
            "INVESTIGATING": {"CONTAINED", "FALSE POSITIVE"},
            "CONTAINED": {"RESOLVED"},
            "RESOLVED": set(),
            "FALSE POSITIVE": set(),
        }

        if new_status != current_status:
            if new_status not in allowed_transitions.get(
                current_status, set()
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status transition: "
                           f"{current_status} -> {new_status}"
                )

            if not alert_data.comment:
                raise HTTPException(
                    status_code=400,
                    detail="A comment is required for status changes"
                )

            if new_status == "FALSE POSITIVE" and not alert_data.reason:
                raise HTTPException(
                    status_code=400,
                    detail="A reason is required for FALSE POSITIVE"
                )

            alert.status = new_status

            audit = AuditLog(
                user_id=current_user.id,
                action="alert_status_changed",
                resource_type="alert",
                resource_id=str(alert.alert_id),
                details=(
                    f"Status changed from {current_status} "
                    f"to {new_status}. "
                    f"Comment: {alert_data.comment}. "
                    f"Reason: {alert_data.reason or 'N/A'}"
                ),
                created_at=datetime.now(timezone.utc),
            )

            db.add(audit)

    # Handle assignment
    if alert_data.assigned_to is not None:
        old_assignee = alert.assigned_to
        alert.assigned_to = alert_data.assigned_to

        audit = AuditLog(
            user_id=current_user.id,
            action="alert_assigned",
            resource_type="alert",
            resource_id=str(alert.alert_id),
            details=(
                f"Assignment changed from "
                f"{old_assignee} to {alert_data.assigned_to}"
            ),
            created_at=datetime.now(timezone.utc),
        )

        db.add(audit)

    db.commit()
    db.refresh(alert)

    return _serialize_alert(alert)


@router.post("/alerts/{alert_id}/promote")
def promote_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("analyst", "lead", "admin"))
):
    """Promote an alert to an incident (spec §5.1).

    Creating the incident and linking the alert happen in one transaction so
    the dashboard can promote with a single click.
    """
    alert = db.query(Alert).filter(
        Alert.alert_id == alert_id
    ).first()

    if not alert:
        raise HTTPException(
            status_code=404,
            detail="Alert not found"
        )

    if alert.incident_id:
        raise HTTPException(
            status_code=400,
            detail=f"Alert already linked to incident {alert.incident_id}"
        )

    last_incident = (
        db.query(Incident)
        .order_by(Incident.incident_id.desc())
        .first()
    )

    next_number = last_incident.incident_id + 1 if last_incident else 1

    incident = Incident(
        incident_code=f"INC-{next_number:04d}",
        title=alert.title,
        description=(
            f"Promoted from alert #{alert.alert_id} "
            f"(rule {alert.rule_id})."
        ),
        severity=alert.severity,
        status="open",
        category=alert.category,
        created_at=datetime.now(timezone.utc),
    )

    if alert.src_ip:
        incident.source_ips = [alert.src_ip]

    if alert.dst_host:
        incident.affected_hosts = [alert.dst_host]

    db.add(incident)
    db.flush()

    alert.incident_id = incident.incident_id

    audit = AuditLog(
        user_id=current_user.id,
        action="alert_promoted",
        resource_type="alert",
        resource_id=str(alert.alert_id),
        details=(
            f"Alert {alert.alert_id} promoted to "
            f"{incident.incident_code}"
        ),
        created_at=datetime.now(timezone.utc),
    )

    db.add(audit)
    db.commit()
    db.refresh(incident)

    return {
        "alert_id": alert.alert_id,
        "incident_id": incident.incident_id,
        "incident_code": incident.incident_code,
        "title": incident.title,
        "severity": incident.severity,
        "status": incident.status,
    }


@router.post("/alerts/{alert_id}/export-evidence")
def export_alert_events_as_evidence(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("lead", "admin"))
):
    import hashlib
    import os
    import uuid
    from datetime import datetime, timezone

    from ..models.alert_event import AlertEvent
    from ..models.event import Event
    from ..models.evidence import Evidence
    from ..models.custody_log import CustodyLog
    from ..models.audit_log import AuditLog

    alert = db.query(Alert).filter(
        Alert.alert_id == alert_id
    ).first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if not alert.incident_id:
        raise HTTPException(
            status_code=400,
            detail="Alert must be linked to an incident before exporting events"
        )

    rows = (
        db.query(Event)
        .join(AlertEvent, AlertEvent.event_id == Event.event_id)
        .filter(AlertEvent.alert_id == alert_id)
        .order_by(Event.timestamp.asc())
        .all()
    )

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No events linked to this alert"
        )

    content = "\n".join(
        event.raw for event in rows
    ) + "\n"

    evidence_path = str(evidence_dir())
    os.makedirs(evidence_path, mode=0o700, exist_ok=True)

    filename = f"alert-{alert_id}-events-{uuid.uuid4().hex}.log"
    storage_path = os.path.join(evidence_path, filename)

    data = content.encode("utf-8")
    file_hash = hashlib.sha256(data).hexdigest()

    with open(storage_path, "wb") as output:
        output.write(data)

    evidence = Evidence(
        incident_id=alert.incident_id,
        filename=filename,
        type="text/plain",
        sha256=file_hash,
        size_bytes=len(data),
        uploaded_by=current_user.id,
        uploaded_at=datetime.now(timezone.utc),
        storage_path=storage_path,
    )

    db.add(evidence)
    db.flush()

    custody = CustodyLog(
        evidence_id=evidence.id,
        user_id=current_user.id,
        action="EXPORT",
        timestamp=datetime.now(timezone.utc),
        notes=f"Raw events exported from alert {alert_id}",
    )

    audit = AuditLog(
        user_id=current_user.id,
        action="alert_events_exported",
        resource_type="alert",
        resource_id=str(alert_id),
        details=f"Exported {len(rows)} raw events as evidence {evidence.id}",
        created_at=datetime.now(timezone.utc),
    )

    db.add(custody)
    db.add(audit)
    db.commit()
    db.refresh(evidence)

    return {
        "alert_id": alert_id,
        "evidence_id": evidence.id,
        "incident_id": evidence.incident_id,
        "filename": evidence.filename,
        "event_count": len(rows),
        "sha256": evidence.sha256,
        "size_bytes": evidence.size_bytes,
    }
