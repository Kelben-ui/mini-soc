"""Backend alert listing, detail, promotion and dashboard stats (phase 7).

Calls the route functions directly (the venv's starlette wants ``httpx2`` and
``TestClient`` is unavailable).  Every ``Query(...)`` default in the route
signature is passed explicitly, because Python would otherwise hand the route
the ``Query`` object rather than the resolved value.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from backend.app.models.alert import Alert
from backend.app.models.alert_event import AlertEvent
from backend.app.models.audit_log import AuditLog
from backend.app.models.event import Event
from backend.app.models.incident import Incident
from backend.app.models.user import User
from backend.app.routers.alerts import get_alert, get_alerts, promote_alert
from backend.app.routers.stats import get_stats


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


def make_alert(db, **overrides):
    now = datetime.now(timezone.utc)

    values = {
        "rule_id": "SSH-BF-001",
        "title": "SSH brute force",
        "severity": "HIGH",
        "status": "NEW",
        "first_seen": now,
        "last_seen": now,
        "src_ip": "203.0.113.5",
        "category": "brute-force",
    }
    values.update(overrides)

    alert = Alert(**values)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def make_event(db, alert, src_ip="203.0.113.5"):
    event = Event(
        event_id=uuid.uuid4().hex,
        timestamp=datetime.now(timezone.utc),
        host="host-a",
        log_type="auth",
        category="brute-force",
        action="login",
        src_ip=src_ip,
        raw="Failed password for root from 203.0.113.5",
    )
    db.add(event)
    db.flush()

    db.add(AlertEvent(alert_id=alert.alert_id, event_id=event.event_id))
    db.commit()
    db.refresh(event)
    return event


def call_list(db, user, **overrides):
    params = {
        "severity": None,
        "status": None,
        "rule_id": None,
        "rule": None,
        "src_ip": None,
        "assigned_to": None,
        "start_time": None,
        "end_time": None,
        "limit": 50,
        "offset": 0,
    }
    params.update(overrides)
    return get_alerts(db=db, current_user=user, **params)


def test_list_returns_pagination_envelope(db):
    user = make_user(db)
    make_alert(db, title="one")
    make_alert(db, title="two")

    result = call_list(db, user, limit=1, offset=0)

    assert set(result) == {"items", "total", "limit", "offset"}
    assert result["total"] >= 2
    assert result["limit"] == 1
    assert len(result["items"]) == 1


def test_list_filters_by_severity_status_and_ip(db):
    user = make_user(db)
    make_alert(db, severity="CRITICAL", status="NEW", src_ip="198.51.100.1")
    make_alert(db, severity="LOW", status="RESOLVED", src_ip="198.51.100.2")

    critical = call_list(db, user, severity="critical")
    assert critical["total"] == 1
    assert critical["items"][0]["severity"] == "CRITICAL"

    resolved = call_list(db, user, status="resolved")
    assert resolved["total"] == 1

    by_ip = call_list(db, user, src_ip="198.51.100.2")
    assert by_ip["total"] == 1
    assert by_ip["items"][0]["src_ip"] == "198.51.100.2"


def test_list_time_filter(db):
    user = make_user(db)
    old = make_alert(db, last_seen=datetime(2020, 1, 1, tzinfo=timezone.utc))
    make_alert(db, last_seen=datetime.now(timezone.utc))

    result = call_list(db, user, start_time=datetime(2024, 1, 1, tzinfo=timezone.utc))

    assert old.alert_id not in [a["alert_id"] for a in result["items"]]


def test_detail_includes_linked_events(db):
    user = make_user(db)
    alert = make_alert(db)
    event = make_event(db, alert)

    payload = get_alert(alert.alert_id, db=db, current_user=user)

    assert payload["alert_id"] == alert.alert_id
    assert payload["dst_host"] is None or isinstance(payload["dst_host"], str)
    assert [e["event_id"] for e in payload["events"]] == [event.event_id]
    assert payload["events"][0]["raw"] == event.raw


def test_promote_creates_and_links_incident(db):
    user = make_user(db, role="lead")
    alert = make_alert(db, rule_id="SQLI-001", title="SQL injection")

    result = promote_alert(alert.alert_id, db=db, current_user=user)

    assert result["incident_id"] is not None
    assert result["incident_code"].startswith("INC-")

    db.expire_all()
    refreshed = db.query(Alert).filter(Alert.alert_id == alert.alert_id).first()
    assert refreshed.incident_id == result["incident_id"]

    assert (
        db.query(AuditLog).filter(AuditLog.action == "alert_promoted").first()
        is not None
    )


def test_promote_rejects_already_linked(db):
    user = make_user(db, role="lead")
    alert = make_alert(db)

    promote_alert(alert.alert_id, db=db, current_user=user)

    with pytest.raises(HTTPException):
        promote_alert(alert.alert_id, db=db, current_user=user)


def test_stats_includes_overview_extras(db):
    user = make_user(db)
    make_alert(db, severity="HIGH", src_ip="203.0.113.9", category="brute-force")
    alert = make_alert(db, severity="HIGH", src_ip="203.0.113.9", category="brute-force")
    make_event(db, alert)

    db.add(
        Incident(
            incident_code=f"INC-{uuid.uuid4().hex[:6]}",
            title="open incident",
            severity="high",
            status="open",
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    stats = get_stats(db=db, current_user=user)

    assert "alerts_over_24h" in stats
    assert len(stats["alerts_over_24h"]) == 24
    assert isinstance(stats["top_source_ips"], list)
    assert isinstance(stats["top_attack_types"], list)
    assert stats["open_incidents"] >= 1
