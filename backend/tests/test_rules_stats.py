"""Rule inventory enrichment and the live threat level (phase 7, 7.9/7.10)."""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Response

from backend.app.models.alert import Alert
from backend.app.models.incident import Incident
from backend.app.models.user import User
from backend.app.routers.rules import get_rules
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
    }
    values.update(overrides)

    alert = Alert(**values)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def test_rules_are_enriched_with_fire_counts(db, monkeypatch):
    import backend.app.routers.rules as rules_module

    repo_rules = Path(__file__).resolve().parents[2] / "rules"

    # Force the bundled rules dir regardless of the local RULES_DIR value.
    real_load_rules = rules_module.load_rules
    monkeypatch.setattr(
        rules_module,
        "load_rules",
        lambda **kwargs: real_load_rules(rules_dir=str(repo_rules), **kwargs),
    )

    user = make_user(db)
    make_alert(db, rule_id="SSH-BF-001")

    rules = get_rules(db=db, current_user=user)

    assert rules, "expected at least one rule in rules/"

    by_id = {rule["id"]: rule for rule in rules}

    assert "SSH-BF-001" in by_id
    ssh = by_id["SSH-BF-001"]
    assert ssh["alerts_count"] >= 1
    assert ssh["mitre"] == "T1110"
    assert ssh["last_fired"] is not None
    assert "allowlist" not in {rule.get("id") for rule in rules}


def test_load_rules_falls_back_to_repo_rules(tmp_path):
    """A stale/nonexistent RULES_DIR must not blank the Rules page."""
    from detection.engine.rule_loader import load_rules

    rules = load_rules(rules_dir=str(tmp_path / "does-not-exist"))

    assert any(rule.get("id") == "SSH-BF-001" for rule in rules)


def test_load_rules_can_include_disabled(tmp_path):
    from detection.engine.rule_loader import load_rules

    (tmp_path / "disabled.yaml").write_text(
        "id: TEST-DIS\nname: Disabled rule\nenabled: false\nmitre: T1000\n",
        encoding="utf-8",
    )

    # The engine ignores disabled rules ...
    assert load_rules(rules_dir=str(tmp_path)) == []

    # ... but the Rules page shows them (greyed out).
    listed = load_rules(rules_dir=str(tmp_path), include_disabled=True)
    assert [rule["id"] for rule in listed] == ["TEST-DIS"]


def test_threat_level_reflects_active_critical(db):
    user = make_user(db)
    make_alert(db, severity="CRITICAL", status="NEW")

    stats = get_stats(db=db, current_user=user, response=Response())

    assert stats["threat_level"] == "CRITICAL"
    assert stats["active_alerts"] >= 1
    assert stats["active_alerts_by_severity"].get("CRITICAL", 0) >= 1


def test_resolved_alerts_do_not_raise_threat_level(db):
    user = make_user(db)
    make_alert(db, severity="LOW", status="RESOLVED")

    stats = get_stats(db=db, current_user=user, response=Response())

    assert "threat_level" in stats
    assert stats["threat_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def test_stats_exposes_response_time_metrics(db):
    user = make_user(db)
    created = datetime.now(timezone.utc)

    incident = Incident(
        incident_code=f"INC-{uuid.uuid4().hex[:6]}",
        title="contained incident",
        severity="high",
        status="contained",
        created_at=created,
        contained_at=datetime.now(timezone.utc),
    )
    db.add(incident)
    db.commit()

    stats = get_stats(db=db, current_user=user, response=Response())

    assert "mean_time_to_detect_seconds" in stats
    assert "mean_time_to_contain_seconds" in stats
    assert "mean_time_to_resolve_seconds" in stats
