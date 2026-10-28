"""Seed a local database with demo data for user-guide screenshots.

Run from the repo root:

    python docs/testing/screenshots/seed_demo.py

By default it builds a throwaway SQLite database
(`demo-screenshots.db` in the working directory, overridable with
``DATABASE_URL``) with:

* three users (`analyst`, `lead`, `admin`, password ``demo-password-123``);
* one normalized event set per detection rule;
* the alerts + chains produced by the **real** detection engine;
* one incident with notes, response actions and status history.

The detection engine only evaluates events within its widest rule window
(300 s), so every event is stamped within the last few minutes. The script is
safe to re-run: it first removes previous demo data for the demo source, and it
reconciles the schema of a pre-existing database with the current models.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

# These must be set before importing anything that reads configuration at
# import time (mini_soc_config loads .env with override=False, so these win).
os.environ.setdefault("DATABASE_URL", "sqlite:///./demo-screenshots.db")
os.environ.setdefault("INGEST_API_KEY", "demo-key")
os.environ.setdefault("JWT_SECRET_KEY", "demo-secret")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "720")

from backend.app.database import Base, SessionLocal, engine  # noqa: E402
from backend.app.models.action import Action  # noqa: E402
from backend.app.models.alert import Alert  # noqa: E402
from backend.app.models.alert_event import AlertEvent  # noqa: E402
from backend.app.models.event import Event  # noqa: E402
from backend.app.models.incident import Incident  # noqa: E402
from backend.app.models.incident_status_history import (  # noqa: E402
    IncidentStatusHistory,
)
from backend.app.models.note import Note  # noqa: E402
from backend.app.models.user import User  # noqa: E402
from backend.app.utils.password import hash_password  # noqa: E402
from detection.engine.engine import run_detection  # noqa: E402
from detection.engine.rule_loader import load_rules  # noqa: E402

DEMO_SOURCE = "203.0.113.66"
SECOND_SOURCE = "198.51.100.23"
DEST_HOST = "soc-01"
DEST_IP = "192.0.2.10"
PASSWORD = "demo-password-123"
INCIDENT_CODE = "INC-2026-0001"

# All timestamps are relative to "now" and stay inside the detection window.
BASE = datetime.now(timezone.utc)


def ago(seconds: float) -> datetime:
    return BASE - timedelta(seconds=seconds)


def make_event(db, *, log_type, category, action, **kwargs):
    event = Event(
        event_id=str(uuid.uuid4()),
        timestamp=kwargs.get("timestamp") or BASE,
        host=kwargs.get("host", DEST_HOST),
        log_type=log_type,
        category=category,
        action=action,
        src_ip=kwargs.get("src_ip", DEMO_SOURCE),
        src_port=kwargs.get("src_port", 51000),
        dst_ip=kwargs.get("dst_ip", DEST_IP),
        dst_port=kwargs.get("dst_port", 80),
        user=kwargs.get("user"),
        outcome=kwargs.get("outcome"),
        details=kwargs.get("details"),
        raw=kwargs.get("raw", "demo event"),
    )
    db.add(event)
    return event


def ensure_users(db):
    users = {}
    for username, role in (
        ("analyst", "analyst"),
        ("lead", "lead"),
        ("admin", "admin"),
    ):
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            user = User(
                username=username,
                password_hash=hash_password(PASSWORD),
                role=role,
            )
            db.add(user)
            db.flush()
        users[username] = user
    return users


def seed_events(db):
    # 10. Port scan (IDS) — oldest, starts the chain.
    make_event(
        db,
        log_type="mini_soc_ids",
        category="network",
        action="port_scan",
        details={"distinct_destination_ports": 24, "signature_id": 9000001},
        raw=f"IDS port scan from {DEMO_SOURCE}",
        timestamp=ago(280),
    )
    # 11. Generic IDS signature (SYN flood signature).
    make_event(
        db,
        log_type="mini_soc_ids",
        category="ids",
        action="ids_alert",
        details={
            "signature_id": 9000003,
            "signature": "MINI-SOC SYN Flood Detected",
            "priority": 2,
        },
        raw="IDS syn flood alert",
        timestamp=ago(275),
    )

    # 1 + 2. SSH brute force, then a success.
    for i in range(12):
        make_event(
            db,
            log_type="auth",
            category="authentication",
            action="ssh_login",
            outcome="failure",
            user="admin",
            dst_port=22,
            raw=f"Failed password for admin from {DEMO_SOURCE} port 51{i:03d} ssh2",
            timestamp=ago(260 - i),
        )
    make_event(
        db,
        log_type="auth",
        category="authentication",
        action="ssh_login",
        outcome="success",
        user="admin",
        dst_port=22,
        raw=f"Accepted password for admin from {DEMO_SOURCE} port 51888 ssh2",
        timestamp=ago(240),
    )

    # 3. Web login brute force.
    for i in range(22):
        make_event(
            db,
            log_type="nginx_access",
            category="web",
            action="http_request",
            outcome="failure",
            details={
                "method": "POST",
                "uri": "/dvwa/login.php",
                "status": 401,
                "user_agent": "Mozilla/5.0",
            },
            raw="POST /dvwa/login.php HTTP/1.1 401",
            timestamp=ago(220 - i),
        )

    # 4. SQL injection.
    make_event(
        db,
        log_type="nginx_access",
        category="web",
        action="http_request",
        details={
            "method": "GET",
            "uri": "/vulnerabilities/sqli/?id=1' OR '1'='1&Submit=Submit",
            "status": 200,
            "user_agent": "sqlmap/1.8",
        },
        raw="GET /vulnerabilities/sqli/?id=1' OR '1'='1 200",
        timestamp=ago(190),
    )
    # 5. XSS.
    make_event(
        db,
        log_type="nginx_access",
        category="web",
        action="http_request",
        details={
            "method": "GET",
            "uri": "/vulnerabilities/xss_r/?name=<script>alert(1)</script>",
            "status": 200,
        },
        raw="GET /vulnerabilities/xss_r/ 200",
        timestamp=ago(188),
    )
    # 6. Command injection.
    make_event(
        db,
        log_type="nginx_access",
        category="web",
        action="http_request",
        details={
            "method": "GET",
            "uri": "/vulnerabilities/exec/?ip=127.0.0.1; id&Submit=Submit",
            "status": 200,
        },
        raw="GET /vulnerabilities/exec/ 200",
        timestamp=ago(186),
    )
    # 7. LFI / traversal.
    make_event(
        db,
        log_type="nginx_access",
        category="web",
        action="http_request",
        details={
            "method": "GET",
            "uri": "/vulnerabilities/fi/?page=../../../../etc/passwd",
            "status": 200,
        },
        raw="GET /vulnerabilities/fi/ 200",
        timestamp=ago(184),
    )
    # 8. Scanner UA.
    make_event(
        db,
        log_type="nginx_access",
        category="web",
        action="http_request",
        details={
            "method": "GET",
            "uri": "/",
            "status": 200,
            "user_agent": "Nikto/2.5.0",
        },
        raw="GET / HTTP/1.1 200 Nikto",
        timestamp=ago(182),
    )
    # 9. HTTP flood (301 redirects) — 305 requests inside 60 s.
    for i in range(305):
        make_event(
            db,
            log_type="nginx_access",
            category="web",
            action="http_request",
            details={"method": "GET", "uri": "/", "status": 301},
            raw="GET / HTTP/1.1 301",
            timestamp=ago(178 - (i % 30)),
        )
    # 12. Unusual outbound.
    make_event(
        db,
        log_type="firewall",
        category="network",
        action="unusual_outbound",
        dst_ip="203.0.113.9",
        dst_port=4444,
        details={"reason": "destination port not allowlisted"},
        raw="SOC_OUT: IN= OUT=eth0 SRC=192.0.2.10 DST=203.0.113.9 DPT=4444",
        timestamp=ago(90),
    )
    # 13. Unusual DNS.
    make_event(
        db,
        log_type="mini_soc_ids",
        category="dns",
        action="unusual_dns",
        dst_port=53,
        details={
            "signature_id": 9000004,
            "query": "aGVsbG8td29ybGQ.exfil.example.net",
        },
        raw="IDS DNS tunneling suspected",
        timestamp=ago(85),
    )

    # Benign background traffic from a second source.
    for i in range(6):
        make_event(
            db,
            log_type="nginx_access",
            category="web",
            action="http_request",
            src_ip=SECOND_SOURCE,
            details={
                "method": "GET",
                "uri": "/",
                "status": 200,
                "user_agent": "Mozilla/5.0",
            },
            raw="GET / HTTP/1.1 200",
            timestamp=ago(40 - i * 3),
        )


def build_incident(db, users, alerts):
    admin = users["admin"]

    incident = Incident(
        incident_code=INCIDENT_CODE,
        title=f"Multi-stage attack from {DEMO_SOURCE}",
        description=(
            f"Reconnaissance from {DEMO_SOURCE} escalated to web exploitation "
            "and SSH brute force against soc-01, ending in a successful login. "
            "Correlated into one chain."
        ),
        severity="CRITICAL",
        status="investigating",
        category="intrusion",
        assigned_to=admin.id,
        affected_hosts=[DEST_HOST],
        source_ips=[DEMO_SOURCE],
        created_at=ago(300),
    )
    db.add(incident)
    db.flush()

    for alert in alerts:
        if alert.src_ip == DEMO_SOURCE:
            alert.incident_id = incident.incident_id

    db.add(
        Note(
            incident_id=incident.incident_id,
            author=admin.id,
            body=(
                "Port scan (24 ports) first, then SQLi / LFI / command-injection "
                "attempts, then a 12-attempt SSH brute force ending in a "
                "successful login as 'admin'. Treating as one chain — suspected "
                "credential compromise."
            ),
            created_at=ago(150),
        )
    )
    db.add(
        Note(
            incident_id=incident.incident_id,
            author=admin.id,
            body="Source blocked; recommend disabling SSH password auth at recovery.",
            created_at=ago(70),
        )
    )

    db.add(
        Action(
            incident_id=incident.incident_id,
            action_type="block IP",
            target=DEMO_SOURCE,
            performed_by=admin.id,
            performed_at=ago(75),
            reason="Confirmed multi-stage attack; source still active.",
            result=f"blocked {DEMO_SOURCE} for 3600s",
            status="executed",
        )
    )
    db.add(
        Action(
            incident_id=incident.incident_id,
            action_type="disable account",
            target="admin",
            performed_by=admin.id,
            performed_at=ago(65),
            reason="SSH credential suspected compromised.",
            result="password reset + authorized_keys rotated",
            status="executed",
        )
    )

    db.add(
        IncidentStatusHistory(
            incident_id=incident.incident_id,
            old_status="open",
            new_status="investigating",
            changed_by=admin.id,
            comment="Correlated alerts into one incident.",
            changed_at=ago(200),
        )
    )

    return incident


def cleanup(db):
    alert_ids = [
        row[0]
        for row in db.query(Alert.alert_id)
        .filter(Alert.src_ip.in_([DEMO_SOURCE, SECOND_SOURCE]))
        .all()
    ]
    if alert_ids:
        db.query(AlertEvent).filter(
            AlertEvent.alert_id.in_(alert_ids)
        ).delete(synchronize_session=False)
        db.query(Alert).filter(Alert.alert_id.in_(alert_ids)).delete(
            synchronize_session=False
        )
    db.query(Event).filter(
        Event.src_ip.in_([DEMO_SOURCE, SECOND_SOURCE])
    ).delete(synchronize_session=False)

    incident = (
        db.query(Incident).filter(Incident.incident_code == INCIDENT_CODE).first()
    )
    if incident is not None:
        iid = incident.incident_id
        db.query(Note).filter(Note.incident_id == iid).delete(
            synchronize_session=False
        )
        db.query(Action).filter(Action.incident_id == iid).delete(
            synchronize_session=False
        )
        db.query(IncidentStatusHistory).filter(
            IncidentStatusHistory.incident_id == iid
        ).delete(synchronize_session=False)
        db.delete(incident)

    db.commit()


def main():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        cleanup(db)

        users = ensure_users(db)
        db.commit()

        seed_events(db)
        db.commit()

        rules = load_rules()
        alert_ids = run_detection(db=db, rules=rules)
        db.commit()

        alerts = (
            db.query(Alert).filter(Alert.alert_id.in_(alert_ids)).all()
            if alert_ids
            else []
        )
        incident = build_incident(db, users, alerts)
        db.commit()

        print(f"Rules loaded   : {len(rules)}")
        print(f"Alerts created : {len(alert_ids)}")
        print(f"Incident       : {incident.incident_code}")
        print(f"Users          : analyst / lead / admin  (password: {PASSWORD})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
