from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException



from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user, require_role
from ..models.alert import Alert
from ..models.audit_log import AuditLog
from ..models.user import User
from ..schemas.alert import AlertUpdate
from ..models.event import Event

router = APIRouter(
    prefix="/api",
    tags=["Alerts"]
)


@router.get("/alerts")
def get_alerts(
    db: Session = Depends(get_db),
    current_user=Depends(require_role("analyst", "lead", "admin"))
):
    alerts = db.query(Alert).order_by(
        Alert.last_seen.desc()
    ).all()

    return [
        {
            "alert_id": alert.alert_id,
            "rule_id": alert.rule_id,
            "title": alert.title,
            "severity": alert.severity,
            "status": alert.status,
            "first_seen": alert.first_seen,
            "last_seen": alert.last_seen,
            "src_ip": alert.src_ip,
            "dst_ip": alert.dst_ip,
            "count": alert.count,
            "chain_id": alert.chain_id,
            "assigned_to": alert.assigned_to,
            "incident_id": alert.incident_id,
        }
        for alert in alerts
    ]


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
        "count": alert.count,
        "chain_id": alert.chain_id,
        "assigned_to": alert.assigned_to,
        "incident_id": alert.incident_id,
    }

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
        "count": alert.count,
        "chain_id": alert.chain_id,
        "assigned_to": alert.assigned_to,
        "incident_id": alert.incident_id,
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

    evidence_dir = "/var/lib/mini-soc/evidence"
    os.makedirs(evidence_dir, mode=0o700, exist_ok=True)

    filename = f"alert-{alert_id}-events-{uuid.uuid4().hex}.log"
    storage_path = os.path.join(evidence_dir, filename)

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
