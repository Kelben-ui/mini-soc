"""Incident detail, notes, evidence, timeline, metrics and editing (7.8)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from backend.app.models.action import Action
from backend.app.models.alert import Alert
from backend.app.models.audit_log import AuditLog
from backend.app.models.custody_log import CustodyLog
from backend.app.models.evidence import Evidence
from backend.app.models.incident import Incident
from backend.app.models.incident_status_history import IncidentStatusHistory
from backend.app.models.note import Note
from backend.app.models.user import User
from backend.app.routers.incidents import (
    add_note,
    get_custody,
    get_evidence,
    get_incident,
    get_notes,
    get_timeline,
    update_incident,
    update_incident_status,
)
from backend.app.schemas.incident import IncidentStatusUpdate, IncidentUpdate, NoteCreate


def make_user(db, role="analyst"):
    user = User(
        username=f"user-{role}-{uuid.uuid4().hex[:12]}",
        password_hash="x",
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_incident(db, **overrides):
    values = {
        "incident_code": f"INC-{uuid.uuid4().hex[:6]}",
        "title": "Suspicious activity",
        "severity": "high",
        "status": "open",
        "created_at": datetime.now(timezone.utc),
    }
    values.update(overrides)

    incident = Incident(**values)
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


def link_alert(db, incident, first_seen):
    alert = Alert(
        rule_id="SSH-BF-001",
        title="SSH brute force",
        severity="HIGH",
        status="NEW",
        first_seen=first_seen,
        last_seen=first_seen,
        incident_id=incident.incident_id,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def test_get_incident_computes_ttd(db):
    user = make_user(db)
    created = datetime.now(timezone.utc)
    incident = make_incident(db, created_at=created)
    link_alert(db, incident, created - timedelta(seconds=120))

    payload = get_incident(incident.incident_id, db=db, current_user=user)

    assert payload["alert_count"] == 1
    assert payload["ttd_seconds"] == 120
    assert payload["ttc_seconds"] is None
    assert payload["ttr_seconds"] is None


def test_notes_roundtrip(db):
    user = make_user(db)
    incident = make_incident(db)

    add_note(
        incident.incident_id,
        NoteCreate(body="Initial triage complete"),
        db=db,
        current_user=user,
    )

    notes = get_notes(incident.incident_id, db=db, current_user=user)

    assert len(notes) == 1
    assert notes[0]["body"] == "Initial triage complete"
    assert notes[0]["author"] == user.id


def test_evidence_and_custody_listing(db):
    user = make_user(db)
    incident = make_incident(db)

    evidence = Evidence(
        incident_id=incident.incident_id,
        filename="capture.pcap",
        type="application/octet-stream",
        sha256="a" * 64,
        size_bytes=128,
        uploaded_by=user.id,
        uploaded_at=datetime.now(timezone.utc),
        storage_path="/tmp/capture.pcap",
    )
    db.add(evidence)
    db.flush()

    db.add(
        CustodyLog(
            evidence_id=evidence.id,
            user_id=user.id,
            action="UPLOAD",
            timestamp=datetime.now(timezone.utc),
            notes="uploaded",
        )
    )
    db.commit()

    listed = get_evidence(incident.incident_id, db=db, current_user=user)
    assert [item["filename"] for item in listed] == ["capture.pcap"]

    custody = get_custody(evidence.id, db=db, current_user=user)
    assert len(custody) == 1
    assert custody[0]["action"] == "UPLOAD"


def test_timeline_merges_sources_in_order(db):
    user = make_user(db)
    incident = make_incident(db)

    base = datetime.now(timezone.utc)

    db.add(
        IncidentStatusHistory(
            incident_id=incident.incident_id,
            old_status="open",
            new_status="investigating",
            changed_by=user.id,
            comment="picking this up",
            changed_at=base,
        )
    )
    db.add(
        Note(
            incident_id=incident.incident_id,
            author=user.id,
            body="note body",
            created_at=datetime.now(timezone.utc),
        )
    )
    db.add(
        Action(
            incident_id=incident.incident_id,
            action_type="block ip",
            target="203.0.113.9",
            performed_by=user.id,
            performed_at=datetime.now(timezone.utc),
            reason="confirmed",
            result="recorded",
        )
    )
    db.commit()

    timeline = get_timeline(incident.incident_id, db=db, current_user=user)

    types = [item["type"] for item in timeline["items"]]
    assert "status" in types
    assert "note" in types
    assert "action" in types

    timestamps = [item["timestamp"] for item in timeline["items"]]
    assert timestamps == sorted(timestamps)


def test_update_incident_edits_and_audits(db):
    user = make_user(db, role="lead")
    incident = make_incident(db)

    payload = update_incident(
        incident.incident_id,
        IncidentUpdate(root_cause="Weak password", lessons_learned="Enable MFA"),
        db=db,
        current_user=user,
    )

    assert payload["root_cause"] == "Weak password"
    assert payload["lessons_learned"] == "Enable MFA"
    assert (
        db.query(AuditLog).filter(AuditLog.action == "incident_updated").first()
        is not None
    )


def test_update_incident_assignment_requires_lead(db):
    analyst = make_user(db, role="analyst")
    incident = make_incident(db)

    with pytest.raises(HTTPException) as exc:
        update_incident(
            incident.incident_id,
            IncidentUpdate(assigned_to=1),
            db=db,
            current_user=analyst,
        )

    assert exc.value.status_code == 403


def test_status_transitions_stamp_contained_and_resolved(db):
    user = make_user(db, role="lead")
    incident = make_incident(db)

    contained = update_incident_status(
        incident.incident_id,
        IncidentStatusUpdate(status="contained", comment="isolated host"),
        db=db,
        current_user=user,
    )
    assert contained["contained_at"] is not None

    payload = get_incident(incident.incident_id, db=db, current_user=user)
    assert payload["ttc_seconds"] is not None

    update_incident_status(
        incident.incident_id,
        IncidentStatusUpdate(status="resolved", comment="cleaned up"),
        db=db,
        current_user=user,
    )

    refreshed = get_incident(incident.incident_id, db=db, current_user=user)
    assert refreshed["resolved_at"] is not None
    assert refreshed["ttr_seconds"] is not None

    history = (
        db.query(IncidentStatusHistory)
        .filter(IncidentStatusHistory.incident_id == incident.incident_id)
        .all()
    )
    assert len(history) == 2


def test_update_incident_assignee_requires_existing_user(db):
    user = make_user(db, role="lead")
    incident = make_incident(db)

    with pytest.raises(HTTPException) as exc:
        update_incident(
            incident.incident_id,
            IncidentUpdate(assigned_to=999999),
            db=db,
            current_user=user,
        )

    assert exc.value.status_code == 404
