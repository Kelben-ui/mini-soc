"""Attack-chain listing/detail/promotion (phase 7, task 7.7).

As elsewhere in this suite the route functions are called directly, so every
``Query`` default is passed explicitly.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from backend.app.models.alert import Alert
from backend.app.models.audit_log import AuditLog
from backend.app.models.incident import Incident
from backend.app.models.user import User
from backend.app.routers.chains import get_chain, get_chains, promote_chain


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


def make_alert(db, chain_id, **overrides):
    now = datetime.now(timezone.utc)

    values = {
        "rule_id": "SSH-BF-001",
        "title": "SSH brute force",
        "severity": "HIGH",
        "status": "NEW",
        "first_seen": now,
        "last_seen": now,
        "src_ip": "203.0.113.5",
        "category": "authentication",
        "chain_id": chain_id,
    }
    values.update(overrides)

    alert = Alert(**values)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def test_get_chains_groups_by_chain_id(db):
    user = make_user(db)
    make_alert(db, 9001, severity="HIGH")
    make_alert(db, 9001, severity="CRITICAL", category="web", rule_id="SQLI-001")
    make_alert(db, 9002, severity="LOW")

    result = get_chains(only_unpromoted=False, since=None, db=db, current_user=user)

    chains = {item["chain_id"]: item for item in result["items"]}

    assert 9001 in chains
    assert chains[9001]["alert_count"] == 2
    assert chains[9001]["max_severity"] == "CRITICAL"
    assert "web" in chains[9001]["categories"]
    assert result["total"] >= 2


def test_get_chain_detail_lists_alerts_in_order(db):
    user = make_user(db)
    now = datetime.now(timezone.utc)
    first = make_alert(db, 9003, first_seen=now - timedelta(minutes=5))
    second = make_alert(db, 9003, first_seen=now)

    detail = get_chain(9003, db=db, current_user=user)

    assert detail["chain_id"] == 9003
    assert [a["alert_id"] for a in detail["alerts"]] == [first.alert_id, second.alert_id]


def test_get_chain_unknown_is_404(db):
    user = make_user(db)

    with pytest.raises(HTTPException) as exc:
        get_chain(424242, db=db, current_user=user)

    assert exc.value.status_code == 404


def test_promote_chain_links_every_alert(db):
    user = make_user(db, role="lead")
    first = make_alert(db, 9004, src_ip="198.51.100.7", category="authentication")
    second = make_alert(db, 9004, src_ip="198.51.100.7", category="web", dst_host="web-1")

    result = promote_chain(9004, db=db, current_user=user)

    assert result["incident_code"].startswith("INC-")
    assert result["alert_count"] == 2

    db.expire_all()
    incident = (
        db.query(Incident)
        .filter(Incident.incident_id == result["incident_id"])
        .first()
    )
    assert incident is not None
    assert "198.51.100.7" in incident.source_ips
    assert "web-1" in incident.affected_hosts

    for alert_id in (first.alert_id, second.alert_id):
        refreshed = db.query(Alert).filter(Alert.alert_id == alert_id).first()
        assert refreshed.incident_id == result["incident_id"]

    assert (
        db.query(AuditLog)
        .filter(AuditLog.action == "attack_chain_promoted")
        .first()
        is not None
    )


def test_promote_chain_rejects_already_promoted(db):
    user = make_user(db, role="lead")
    make_alert(db, 9005)

    promote_chain(9005, db=db, current_user=user)

    with pytest.raises(HTTPException) as exc:
        promote_chain(9005, db=db, current_user=user)

    assert exc.value.status_code == 409
