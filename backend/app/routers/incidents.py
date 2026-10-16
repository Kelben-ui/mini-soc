from datetime import datetime, timezone
import hashlib
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from mini_soc_config import evidence_dir
from ..utils.report_html import CSP_META, esc, esc_list
from ..models.alert import Alert
from ..models.note import Note
from ..models.evidence import Evidence
from ..models.action import Action
from ..models.user import User
from ..database import get_db
from ..dependencies import get_current_user, require_role
from ..models.incident import Incident
from ..models.incident_status_history import IncidentStatusHistory
from ..models.audit_log import AuditLog
from ..models.custody_log import CustodyLog
from ..schemas.incident import (
    IncidentCreate,
    IncidentUpdate,
    NoteCreate,
    EvidenceCreate,
    ActionCreate,
    IncidentStatusUpdate,
)


router = APIRouter(
    prefix="/api",
    tags=["Incidents"]
)

def _as_utc(value):
    """Normalize SQLite's naive datetimes so timestamp maths never fails."""
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value


def _seconds_between(start, end):
    start = _as_utc(start)
    end = _as_utc(end)

    if start is None or end is None:
        return None

    return int((end - start).total_seconds())


def _resolve_actor(user_map, user_id):
    if user_id is None:
        return None
    user = user_map.get(user_id)
    return user.username if user else f"user {user_id}"


def _serialize_incident(db, incident):
    """Full incident payload shared by the list/detail/report views.

    Response metrics are detection-anchored (spec TTD/TTC/TTR):
      * TTD = incident created - earliest linked alert first_seen
      - TTC = contained_at - incident created
      - TTR = (resolved_at or closed_at) - incident created
    ``None`` means the timestamp needed for the metric is not available yet.
    """
    alerts = (
        db.query(Alert)
        .filter(Alert.incident_id == incident.incident_id)
        .order_by(Alert.first_seen.asc())
        .all()
    )

    earliest = min(
        (_as_utc(a.first_seen) for a in alerts if a.first_seen),
        default=None,
    )
    created = _as_utc(incident.created_at)
    resolved = incident.resolved_at or incident.closed_at

    return {
        "incident_id": incident.incident_id,
        "incident_code": incident.incident_code,
        "title": incident.title,
        "description": incident.description,
        "severity": incident.severity,
        "status": incident.status,
        "category": incident.category,
        "assigned_to": incident.assigned_to,
        "affected_hosts": incident.affected_hosts,
        "source_ips": incident.source_ips,
        "created_at": incident.created_at,
        "closed_at": incident.closed_at,
        "contained_at": incident.contained_at,
        "resolved_at": incident.resolved_at,
        "root_cause": incident.root_cause,
        "lessons_learned": incident.lessons_learned,
        "alert_count": len(alerts),
        "alert_ids": [a.alert_id for a in alerts],
        "ttd_seconds": _seconds_between(earliest, created),
        "ttc_seconds": _seconds_between(created, incident.contained_at),
        "ttr_seconds": _seconds_between(created, resolved),
    }


@router.get("/incidents")
def get_incidents(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    incidents = db.query(Incident).all()
    return incidents

@router.post("/incidents")
def create_incident(
    incident_data: IncidentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("analyst", "lead", "admin"))
):
    last_incident = (
	db.query(Incident)
	.order_by(Incident.incident_id.desc())
	.first()
    )

    next_number = (
	last_incident.incident_id + 1
	if last_incident
	else 1
    )
    incident_code = f"INC-{next_number:04d}"
    incident = Incident(
	incident_code=incident_code,
        title=incident_data.title,
        description=incident_data.description,
        severity=incident_data.severity,
        status="open",
        category=incident_data.category,
        assigned_to=incident_data.assigned_to,
	affected_hosts=incident_data.affected_hosts,
	source_ips=incident_data.source_ips,
        created_at=datetime.now(timezone.utc),
    )

    db.add(incident)
    db.commit()
    db.refresh(incident)

    return {
        "incident_id": incident.incident_id,
        "title": incident.title,
        "description": incident.description,
        "severity": incident.severity,
        "status": incident.status,
        "category": incident.category,
        "assigned_to": incident.assigned_to,
        "created_at": incident.created_at,
        "closed_at": incident.closed_at,
        "root_cause": incident.root_cause,
        "lessons_learned": incident.lessons_learned,
	"incident_code": incident.incident_code,
	"affected_hosts": incident.affected_hosts,
	"source_ips": incident.source_ips,
    }

@router.get("/incidents/{incident_id}")
def get_incident(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("analyst", "lead", "admin"))
):
    incident = db.query(Incident).filter(
        Incident.incident_id == incident_id
    ).first()

    if not incident:
        raise HTTPException(
            status_code=404,
            detail="Incident not found"
        )

    return _serialize_incident(db, incident)


@router.patch("/incidents/{incident_id}")
def update_incident(
    incident_id: int,
    incident_data: IncidentUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("analyst", "lead", "admin")),
):
    """Edit the incident narrative fields (task 7.8).

    Narrative fields (description, category, root cause, lessons learned) are
    editable by any analyst; re-assignment is restricted to ``lead``/``admin``
    (spec §5.8).  Every change is written to the audit log.
    """
    incident = db.query(Incident).filter(
        Incident.incident_id == incident_id
    ).first()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    changes = incident_data.model_dump(exclude_unset=True)

    if not changes:
        return _serialize_incident(db, incident)

    if "assigned_to" in incident_data.model_fields_set and current_user.role not in {
        "lead",
        "admin",
    }:
        raise HTTPException(
            status_code=403,
            detail="Only lead or admin can change the assignee",
        )

    if "assigned_to" in incident_data.model_fields_set and incident_data.assigned_to:
        assignee = db.query(User).filter(
            User.id == incident_data.assigned_to
        ).first()

        if not assignee:
            raise HTTPException(status_code=404, detail="User not found")

    fields = ("description", "category", "assigned_to", "root_cause", "lessons_learned")
    changes_made = []

    for field in fields:
        if field not in changes:
            continue

        old_value = getattr(incident, field)
        new_value = changes[field]

        if old_value == new_value:
            continue

        setattr(incident, field, new_value)
        changes_made.append(f"{field}: {old_value!r} -> {new_value!r}")

    if changes_made:
        audit = AuditLog(
            user_id=current_user.id,
            action="incident_updated",
            resource_type="incident",
            resource_id=str(incident.incident_id),
            details="; ".join(changes_made),
            created_at=datetime.now(timezone.utc),
        )
        db.add(audit)

    db.commit()
    db.refresh(incident)

    return _serialize_incident(db, incident)


@router.get("/incidents/{incident_id}/notes")
def get_notes(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("analyst", "lead", "admin"))
):
    incident = db.query(Incident).filter(
        Incident.incident_id == incident_id
    ).first()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    notes = (
        db.query(Note)
        .filter(Note.incident_id == incident_id)
        .order_by(Note.created_at.asc(), Note.id.asc())
        .all()
    )

    return [
        {
            "id": note.id,
            "incident_id": note.incident_id,
            "author": note.author,
            "body": note.body,
            "created_at": note.created_at,
        }
        for note in notes
    ]


@router.get("/incidents/{incident_id}/evidence")
def get_evidence(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("analyst", "lead", "admin"))
):
    incident = db.query(Incident).filter(
        Incident.incident_id == incident_id
    ).first()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    evidence_items = (
        db.query(Evidence)
        .filter(Evidence.incident_id == incident_id)
        .order_by(Evidence.uploaded_at.asc(), Evidence.id.asc())
        .all()
    )

    return [
        {
            "id": item.id,
            "incident_id": item.incident_id,
            "filename": item.filename,
            "type": item.type,
            "sha256": item.sha256,
            "size_bytes": item.size_bytes,
            "uploaded_by": item.uploaded_by,
            "uploaded_at": item.uploaded_at,
        }
        for item in evidence_items
    ]


@router.get("/evidence/{evidence_id}/custody")
def get_custody(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("analyst", "lead", "admin"))
):
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()

    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    entries = (
        db.query(CustodyLog)
        .filter(CustodyLog.evidence_id == evidence_id)
        .order_by(CustodyLog.timestamp.asc(), CustodyLog.id.asc())
        .all()
    )

    return [
        {
            "id": entry.id,
            "evidence_id": entry.evidence_id,
            "user_id": entry.user_id,
            "action": entry.action,
            "timestamp": entry.timestamp,
            "notes": entry.notes,
        }
        for entry in entries
    ]


@router.get("/incidents/{incident_id}/timeline")
def get_timeline(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("analyst", "lead", "admin"))
):
    """Merge status changes, notes, evidence, custody and actions (spec §5.6)."""
    incident = db.query(Incident).filter(
        Incident.incident_id == incident_id
    ).first()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    history = (
        db.query(IncidentStatusHistory)
        .filter(IncidentStatusHistory.incident_id == incident_id)
        .all()
    )
    notes = db.query(Note).filter(Note.incident_id == incident_id).all()
    evidence_items = (
        db.query(Evidence).filter(Evidence.incident_id == incident_id).all()
    )
    actions = db.query(Action).filter(Action.incident_id == incident_id).all()

    evidence_ids = [item.id for item in evidence_items]
    custody_entries = (
        db.query(CustodyLog)
        .filter(CustodyLog.evidence_id.in_(evidence_ids))
        .all()
        if evidence_ids
        else []
    )

    user_ids = (
        {entry.changed_by for entry in history}
        | {note.author for note in notes}
        | {item.uploaded_by for item in evidence_items}
        | {entry.user_id for entry in custody_entries}
        | {action.performed_by for action in actions}
    )

    user_map = {}
    if user_ids:
        for user in db.query(User).filter(User.id.in_(user_ids)).all():
            user_map[user.id] = user

    items = []

    for entry in history:
        items.append(
            {
                "type": "status",
                "timestamp": entry.changed_at,
                "actor": user_map.get(entry.changed_by).username
                if entry.changed_by in user_map
                else None,
                "summary": f"Status changed {entry.old_status} -> {entry.new_status}",
                "details": entry.comment,
            }
        )

    for note in notes:
        items.append(
            {
                "type": "note",
                "timestamp": note.created_at,
                "actor": user_map.get(note.author).username
                if note.author in user_map
                else None,
                "summary": "Investigation note added",
                "details": note.body,
            }
        )

    for item in evidence_items:
        items.append(
            {
                "type": "evidence",
                "timestamp": item.uploaded_at,
                "actor": user_map.get(item.uploaded_by).username
                if item.uploaded_by in user_map
                else None,
                "summary": f"Evidence uploaded: {item.filename}",
                "details": item.sha256,
            }
        )

    for entry in custody_entries:
        items.append(
            {
                "type": "custody",
                "timestamp": entry.timestamp,
                "actor": user_map.get(entry.user_id).username
                if entry.user_id in user_map
                else None,
                "summary": f"Evidence custody: {entry.action}",
                "details": entry.notes,
            }
        )

    for action in actions:
        items.append(
            {
                "type": "action",
                "timestamp": action.performed_at,
                "actor": user_map.get(action.performed_by).username
                if action.performed_by in user_map
                else None,
                "summary": f"Response action: {action.action_type} -> {action.target}",
                "details": action.result,
            }
        )

    items.sort(key=lambda item: _as_utc(item["timestamp"]) or datetime.min.replace(tzinfo=timezone.utc))

    return {"incident_id": incident_id, "items": items}


@router.post("/incidents/{incident_id}/notes")
def add_note(
    incident_id: int,
    note_data: NoteCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("analyst", "lead", "admin"))
):
    incident = db.query(Incident).filter(
        Incident.incident_id == incident_id
    ).first()

    if not incident:
        raise HTTPException(
            status_code=404,
            detail="Incident not found"
        )

    note = Note(
        incident_id=incident_id,
        author=current_user.id,
        body=note_data.body,
        created_at=datetime.now(timezone.utc),
    )

    db.add(note)
    db.commit()
    db.refresh(note)

    return {
        "id": note.id,
        "incident_id": note.incident_id,
        "author": note.author,
        "body": note.body,
        "created_at": note.created_at,
    }



@router.post("/incidents/{incident_id}/evidence")
async def add_evidence(
    incident_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_role("analyst", "lead", "admin"))
):
    incident = db.query(Incident).filter(
        Incident.incident_id == incident_id
    ).first()

    if not incident:
        raise HTTPException(
            status_code=404,
            detail="Incident not found"
        )

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required"
        )

    safe_filename = os.path.basename(file.filename)

    evidence_id = uuid.uuid4().hex
    storage_filename = f"{evidence_id}_{safe_filename}"

    storage_dir = str(evidence_dir())
    os.makedirs(storage_dir, mode=0o700, exist_ok=True)
    storage_path = os.path.join(storage_dir, storage_filename)

    sha256 = hashlib.sha256()
    size_bytes = 0

    try:
        with open(storage_path, "wb") as output:
            while True:
                chunk = await file.read(1024 * 1024)

                if not chunk:
                    break

                sha256.update(chunk)
                size_bytes += len(chunk)
                output.write(chunk)

    except Exception:
        if os.path.exists(storage_path):
            os.remove(storage_path)

        raise HTTPException(
            status_code=500,
            detail="Failed to store evidence"
        )

    file_hash = sha256.hexdigest()

    evidence = Evidence(
        incident_id=incident_id,
        filename=safe_filename,
        type=file.content_type or "application/octet-stream",
        sha256=file_hash,
        size_bytes=size_bytes,
        uploaded_by=current_user.id,
        uploaded_at=datetime.now(timezone.utc),
        storage_path=storage_path,
    )

    db.add(evidence)
    db.flush()

    custody = CustodyLog(
        evidence_id=evidence.id,
        user_id=current_user.id,
        action="UPLOAD",
        timestamp=datetime.now(timezone.utc),
        notes="Evidence uploaded",
    )

    audit = AuditLog(
        user_id=current_user.id,
        action="evidence_uploaded",
        resource_type="evidence",
        resource_id=str(evidence.id),
        details=f"Evidence uploaded for incident {incident_id}",
        created_at=datetime.now(timezone.utc),
    )

    db.add(custody)
    db.add(audit)
    db.commit()
    db.refresh(evidence)

    return {
        "id": evidence.id,
        "incident_id": evidence.incident_id,
        "filename": evidence.filename,
        "type": evidence.type,
        "sha256": evidence.sha256,
        "size_bytes": evidence.size_bytes,
        "uploaded_by": evidence.uploaded_by,
        "uploaded_at": evidence.uploaded_at,
    }


@router.post("/incidents/{incident_id}/actions")
def add_action(
    incident_id: int,
    action_data: ActionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("lead", "admin"))
):
    incident = db.query(Incident).filter(
        Incident.incident_id == incident_id
    ).first()

    if not incident:
        raise HTTPException(
            status_code=404,
            detail="Incident not found"
        )

    action = Action(
        incident_id=incident_id,
        action_type=action_data.action_type,
        target=action_data.target,
        performed_by=current_user.id,
        performed_at=datetime.now(timezone.utc),
        reason=action_data.reason,
        result=action_data.result,
    )

    db.add(action)
    db.commit()
    db.refresh(action)

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


@router.get("/incidents/{incident_id}/actions")
def get_actions(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("analyst", "lead", "admin"))
):
    incident = db.query(Incident).filter(
        Incident.incident_id == incident_id
    ).first()

    if not incident:
        raise HTTPException(
            status_code=404,
            detail="Incident not found"
        )

    actions = db.query(Action).filter(
        Action.incident_id == incident_id
    ).order_by(Action.id.asc()).all()

    return [
        {
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
        for action in actions
    ]

@router.get("/incidents/{incident_id}/report")
def get_incident_report(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("analyst", "lead", "admin"))
):
    from fastapi.responses import HTMLResponse

    incident = db.query(Incident).filter(
        Incident.incident_id == incident_id
    ).first()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    notes = db.query(Note).filter(
        Note.incident_id == incident_id
    ).all()

    evidence = db.query(Evidence).filter(
        Evidence.incident_id == incident_id
    ).all()

    actions = db.query(Action).filter(
        Action.incident_id == incident_id
    ).all()

    history = db.query(IncidentStatusHistory).filter(
        IncidentStatusHistory.incident_id == incident_id
    ).order_by(IncidentStatusHistory.changed_at.asc()).all()

    timeline = []

    for item in history:
        timeline.append(
            f"<li><strong>{esc(item.changed_at)}</strong> — "
            f"Status changed from {esc(item.old_status)} to {esc(item.new_status)}. "
            f"{esc(item.comment)}</li>"
        )

    for note in notes:
        timeline.append(
            f"<li><strong>Note</strong> — {esc(note.body)}</li>"
        )

    for item in evidence:
        timeline.append(
            f"<li><strong>Evidence uploaded</strong> — "
            f"{esc(item.filename)} "
            f"(SHA-256: {esc(item.sha256)})</li>"
        )

    for action in actions:
        timeline.append(
            f"<li><strong>Action</strong> — "
            f"{esc(action.action_type)} on {esc(action.target)}: "
            f"{esc(action.result)}</li>"
        )

    evidence_rows = "".join(
        f"""
        <tr>
            <td>{esc(item.id)}</td>
            <td>{esc(item.filename)}</td>
            <td>{esc(item.type)}</td>
            <td>{esc(item.size_bytes)}</td>
            <td>{esc(item.sha256)}</td>
        </tr>
        """
        for item in evidence
    )

    action_rows = "".join(
        f"""
        <tr>
            <td>{esc(item.action_type)}</td>
            <td>{esc(item.target)}</td>
            <td>{esc(item.reason)}</td>
            <td>{esc(item.result)}</td>
        </tr>
        """
        for item in actions
    )

    timeline_html = "".join(timeline)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        {CSP_META}
        <title>Incident Report {esc(incident.incident_code)}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 40px;
                line-height: 1.5;
            }}
            h1, h2 {{
                margin-bottom: 10px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 25px;
            }}
            th, td {{
                border: 1px solid #ccc;
                padding: 8px;
                text-align: left;
                vertical-align: top;
            }}
            th {{
                background: #f2f2f2;
            }}
            .section {{
                margin-top: 30px;
            }}
        </style>
    </head>

    <body>

        <h1>Mini SOC Incident Report</h1>

        <h2>Incident Summary</h2>

        <table>
            <tr><th>Incident ID</th><td>{esc(incident.incident_code)}</td></tr>
            <tr><th>Title</th><td>{esc(incident.title)}</td></tr>
            <tr><th>Description</th><td>{esc(incident.description)}</td></tr>
            <tr><th>Severity</th><td>{esc(incident.severity)}</td></tr>
            <tr><th>Status</th><td>{esc(incident.status)}</td></tr>
            <tr><th>Category</th><td>{esc(incident.category)}</td></tr>
            <tr><th>Assigned Analyst</th><td>{esc(incident.assigned_to)}</td></tr>
            <tr><th>Created At</th><td>{esc(incident.created_at)}</td></tr>
            <tr><th>Closed At</th><td>{esc(incident.closed_at)}</td></tr>
            <tr><th>Affected Hosts</th><td>{esc_list(incident.affected_hosts)}</td></tr>
            <tr><th>Source IPs</th><td>{esc_list(incident.source_ips)}</td></tr>
        </table>

        <div class="section">
            <h2>Timeline</h2>
            <ul>
                {timeline_html}
            </ul>
        </div>

        <div class="section">
            <h2>Evidence</h2>

            <table>
                <tr>
                    <th>ID</th>
                    <th>Filename</th>
                    <th>Type</th>
                    <th>Size</th>
                    <th>SHA-256</th>
                </tr>
                {evidence_rows}
            </table>
        </div>

        <div class="section">
            <h2>Actions</h2>

            <table>
                <tr>
                    <th>Action</th>
                    <th>Target</th>
                    <th>Reason</th>
                    <th>Result</th>
                </tr>
                {action_rows}
            </table>
        </div>

        <div class="section">
            <h2>Root Cause</h2>
            <p>{esc(incident.root_cause) or "Not documented."}</p>
        </div>

        <div class="section">
            <h2>Lessons Learned</h2>
            <p>{esc(incident.lessons_learned) or "Not documented."}</p>
        </div>

    </body>
    </html>
    """

    audit = AuditLog(
        user_id=current_user.id,
        action="incident_report_viewed",
        resource_type="incident",
        resource_id=str(incident.incident_id),
        details=f"Incident report viewed for {incident.incident_code}",
        created_at=datetime.now(timezone.utc),
    )

    db.add(audit)
    db.commit()

    return HTMLResponse(content=html)

@router.patch("/incidents/{incident_id}/status")
def update_incident_status(
    incident_id: int,
    status_data: IncidentStatusUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("lead", "admin"))
):
    incident = db.query(Incident).filter(
        Incident.incident_id == incident_id
    ).first()

    if not incident:
        raise HTTPException(
            status_code=404,
            detail="Incident not found"
        )

    current_status = incident.status.lower()
    new_status = status_data.status.lower()

    allowed_transitions = {
        "open": {"investigating", "contained", "closed"},
        "investigating": {"contained", "closed"},
        "contained": {"resolved"},
        "resolved": {"closed"},
        "closed": set(),
    }

    if new_status not in allowed_transitions.get(current_status, set()):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition: {current_status} -> {new_status}"
        )

    if new_status == "closed" and current_user.role not in {
        "lead",
        "admin",
    }:
        raise HTTPException(
            status_code=403,
            detail="Only lead or admin can close incidents"
        )

    now = datetime.now(timezone.utc)

    old_status = incident.status
    incident.status = new_status

    # Response-time metrics (task 7.8): stamp the transition timestamps so the
    # dashboard can render TTC/TTR.  ``closed_at`` keeps its existing meaning.
    if new_status == "contained" and incident.contained_at is None:
        incident.contained_at = now

    if new_status == "resolved" and incident.resolved_at is None:
        incident.resolved_at = now

    if new_status == "closed":
        incident.closed_at = now

    history = IncidentStatusHistory(
        incident_id=incident.incident_id,
        old_status=old_status,
        new_status=new_status,
        changed_by=current_user.id,
        comment=status_data.comment,
        changed_at=datetime.now(timezone.utc),
    )

    audit = AuditLog(
        user_id=current_user.id,
        action="incident_status_changed",
        resource_type="incident",
        resource_id=str(incident.incident_id),
        details=(
            f"Status changed from {old_status} to {new_status}. "
            f"Comment: {status_data.comment}"
        ),
        created_at=datetime.now(timezone.utc),
    )

    db.add(history)
    db.add(audit)
    db.commit()
    db.refresh(incident)

    return {
        "incident_id": incident.incident_id,
        "incident_code": incident.incident_code,
        "status": incident.status,
        "closed_at": incident.closed_at,
        "contained_at": incident.contained_at,
        "resolved_at": incident.resolved_at,
        "changed_by": current_user.id,
        "comment": status_data.comment,
    }


@router.post("/evidence/{evidence_id}/verify")
def verify_evidence(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("lead", "admin"))
):
    evidence = db.query(Evidence).filter(
        Evidence.id == evidence_id
    ).first()

    if not evidence:
        raise HTTPException(
            status_code=404,
            detail="Evidence not found"
        )

    if not os.path.exists(evidence.storage_path):
        raise HTTPException(
            status_code=404,
            detail="Evidence file not found"
        )

    sha256 = hashlib.sha256()
    size_bytes = 0

    with open(evidence.storage_path, "rb") as file:
        while True:
            chunk = file.read(1024 * 1024)

            if not chunk:
                break

            sha256.update(chunk)
            size_bytes += len(chunk)

    calculated_hash = sha256.hexdigest()

    verified = (
        calculated_hash == evidence.sha256
        and size_bytes == evidence.size_bytes
    )

    custody = CustodyLog(
        evidence_id=evidence.id,
        user_id=current_user.id,
        action="VERIFY",
        timestamp=datetime.now(timezone.utc),
        notes=f"Evidence verification: {'PASSED' if verified else 'FAILED'}",
    )

    audit = AuditLog(
        user_id=current_user.id,
        action="evidence_verified",
        resource_type="evidence",
        resource_id=str(evidence.id),
        details=f"Verification {'passed' if verified else 'failed'}",
        created_at=datetime.now(timezone.utc),
    )

    db.add(custody)
    db.add(audit)
    db.commit()

    return {
        "evidence_id": evidence.id,
        "verified": verified,
        "stored_sha256": evidence.sha256,
        "calculated_sha256": calculated_hash,
        "stored_size_bytes": evidence.size_bytes,
        "calculated_size_bytes": size_bytes,
    }

@router.get("/evidence/{evidence_id}/download")
def download_evidence(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("analyst", "lead", "admin"))
):
    from fastapi.responses import FileResponse

    evidence = db.query(Evidence).filter(
        Evidence.id == evidence_id
    ).first()

    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    if not os.path.exists(evidence.storage_path):
        raise HTTPException(status_code=404, detail="Evidence file not found")

    custody = CustodyLog(
        evidence_id=evidence.id,
        user_id=current_user.id,
        action="DOWNLOAD",
        timestamp=datetime.now(timezone.utc),
        notes="Evidence downloaded",
    )

    audit = AuditLog(
        user_id=current_user.id,
        action="evidence_downloaded",
        resource_type="evidence",
        resource_id=str(evidence.id),
        details=f"Evidence downloaded: {evidence.filename}",
        created_at=datetime.now(timezone.utc),
    )

    db.add(custody)
    db.add(audit)
    db.commit()

    # Always hand evidence back as an opaque download.  The stored
    # ``evidence.type`` is attacker-influenced (it comes from the upload), so
    # serving it verbatim would let an uploaded .html/.svg render and execute
    # in the app's origin (stored XSS).  octet-stream + attachment prevents it.
    return FileResponse(
        path=evidence.storage_path,
        filename=evidence.filename,
        media_type="application/octet-stream",
        headers={"X-Content-Type-Options": "nosniff"},
    )
