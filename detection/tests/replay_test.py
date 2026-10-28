from datetime import datetime, timedelta, timezone
import os
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.app.database import SessionLocal, Base, engine
from backend.app.models.event import Event
from backend.app.models.alert import Alert
from backend.app.models.alert_event import AlertEvent
from backend.app.models import (
    user,
    event as _event_model,
    alert as _alert_model,
    alert_event as _alert_event_model,
    incident,
    note,
    evidence,
    custody_log,
    action,
    audit_log,
    incident_status_history,
)

Base.metadata.create_all(bind=engine)

from detection.engine.engine import run_detection
from detection.engine.rule_loader import load_rules


TEST_SOURCE = "192.0.2.100"
TEST_DESTINATION = "192.0.2.10"


def make_event(
    db,
    *,
    log_type,
    category,
    action,
    outcome=None,
    details=None,
    raw="test event",
    src_ip=TEST_SOURCE,
    src_port=50000,
    dst_ip=TEST_DESTINATION,
    dst_port=80,
    timestamp=None,
):
    event = Event(
        event_id=str(uuid.uuid4()),
        timestamp=timestamp or datetime.now(timezone.utc),
        host="test-host",
        log_type=log_type,
        category=category,
        action=action,
        src_ip=src_ip,
        src_port=src_port,
        dst_ip=dst_ip,
        dst_port=dst_port,
        user=None,
        outcome=outcome,
        details=details,
        raw=raw,
    )

    db.add(event)

    return event


def main():
    db = SessionLocal()
    # Remove any previous replay-test data using the dedicated
    # test source before starting a new replay.
    db.query(AlertEvent).filter(
        AlertEvent.event_id.in_(
            db.query(Event.event_id).filter(
                Event.src_ip == TEST_SOURCE
            )
        )
    ).delete(synchronize_session=False)

    db.query(Alert).filter(
        Alert.src_ip == TEST_SOURCE
    ).delete(synchronize_session=False)

    db.query(Event).filter(
        Event.src_ip == TEST_SOURCE
    ).delete(synchronize_session=False)

    db.commit()
    created_event_ids = []
    created_alert_ids = []

    try:
        now = datetime.now(timezone.utc)

        print("Creating replay test events...")

        # ---------------------------------------------------------
        # 1. SSH brute force
        # ---------------------------------------------------------

        for i in range(10):
            event = make_event(
                db,
                log_type="auth",
                category="authentication",
                action="ssh_login",
                outcome="failure",
                raw="Failed SSH login",
                timestamp=now - timedelta(seconds=i),
            )

            created_event_ids.append(event.event_id)

        # ---------------------------------------------------------
        # 2. Successful SSH login after brute force
        # ---------------------------------------------------------

        event = make_event(
            db,
            log_type="auth",
            category="authentication",
            action="ssh_login",
            outcome="success",
            raw="Successful SSH login",
            timestamp=now + timedelta(seconds=1),
        )

        created_event_ids.append(event.event_id)

        # ---------------------------------------------------------
        # 3. Web brute force
        # ---------------------------------------------------------

        for i in range(20):
            event = make_event(
                db,
                log_type="nginx_access",
                category="web",
                action="http_request",
                outcome="failure",
                details={
                    "method": "POST",
                    "uri": "/dvwa/login.php",
                    "user_agent": "Mozilla/5.0",
                },
                raw="POST /dvwa/login.php HTTP/1.1 401",
                timestamp=now - timedelta(seconds=i),
            )

            created_event_ids.append(event.event_id)

        # ---------------------------------------------------------
        # 4. SQL injection
        # ---------------------------------------------------------

        for i in range(3):
            event = make_event(
                db,
                log_type="nginx_access",
                category="web",
                action="http_request",
                details={
                    "method": "GET",
                    "uri": f"/vulnerabilities/sqli/?id=1' OR '1'='1&x={i}",
                },
                raw="GET /vulnerabilities/sqli/?id=1' OR '1'='1'",
                timestamp=now - timedelta(seconds=i),
            )

            created_event_ids.append(event.event_id)

        # ---------------------------------------------------------
        # 5. XSS
        # ---------------------------------------------------------

        for i in range(3):
            event = make_event(
                db,
                log_type="nginx_access",
                category="web",
                action="http_request",
                details={
                    "method": "GET",
                    "uri": f"/vulnerabilities/xss_r/?name=<script>alert(1)</script>&x={i}",
                },
                raw="GET XSS payload",
                timestamp=now - timedelta(seconds=i),
            )

            created_event_ids.append(event.event_id)

        # ---------------------------------------------------------
        # 6. Command injection
        # ---------------------------------------------------------

        event = make_event(
            db,
            log_type="nginx_access",
            category="web",
            action="http_request",
            details={
                "method": "GET",
                "uri": "/vulnerabilities/exec/?ip=127.0.0.1; whoami",
            },
            raw="GET command injection payload",
            timestamp=now,
        )

        created_event_ids.append(event.event_id)

        # ---------------------------------------------------------
        # 7. Directory traversal / LFI
        # ---------------------------------------------------------

        for i in range(3):
            event = make_event(
                db,
                log_type="nginx_access",
                category="web",
                action="http_request",
                details={
                    "method": "GET",
                    "uri": f"/vulnerabilities/?file=../../etc/passwd&x={i}",
                },
                raw="GET ../../etc/passwd",
                timestamp=now - timedelta(seconds=i),
            )

            created_event_ids.append(event.event_id)

        # ---------------------------------------------------------
        # 8. Scanner user-agent
        # ---------------------------------------------------------

        for i in range(3):
            event = make_event(
                db,
                log_type="nginx_access",
                category="web",
                action="http_request",
                details={
                    "method": "GET",
                    "uri": f"/?x={i}",
                    "user_agent": "sqlmap/1.8",
                },
                raw="GET / HTTP/1.1 sqlmap",
                timestamp=now - timedelta(seconds=i),
            )

            created_event_ids.append(event.event_id)

        # ---------------------------------------------------------
        # 9. HTTP flood
        # ---------------------------------------------------------

        for i in range(301):
            event = make_event(
                db,
                log_type="nginx_access",
                category="web",
                action="http_request",
                details={
                   "method": "GET",
                   "uri": "/",
                   "status": 301,
                },
                raw="GET / HTTP/1.1",
                timestamp=now - timedelta(seconds=i % 30),
            )

            created_event_ids.append(event.event_id)

        # ---------------------------------------------------------
        # 10. Port scan
        # ---------------------------------------------------------

        event = make_event(
            db,
            log_type="ids",
            category="network",
            action="port_scan",
            details={
                "distinct_destination_ports": 20,
            },
            raw="IDS detected port scan",
        )

        created_event_ids.append(event.event_id)

        # ---------------------------------------------------------
        # 11. IDS signature
        # ---------------------------------------------------------

        event = make_event(
            db,
            log_type="ids",
            category="ids",
            action="ids_alert",
            details={
                "signature": "TEST IDS SIGNATURE",
                "priority": 1,
            },
            raw="IDS signature alert",
        )

        created_event_ids.append(event.event_id)

        # ---------------------------------------------------------
        # 12. Unusual outbound connection
        # ---------------------------------------------------------

        for i in range(3):
            event = make_event(
                db,
                log_type="firewall",
                category="network",
                action="unusual_outbound",
                dst_port=4444,
                details={
                    "reason": "destination port not allowlisted",
                },
                raw="Firewall unusual outbound connection",
                timestamp=now - timedelta(seconds=i),
            )

            created_event_ids.append(event.event_id)

        # ---------------------------------------------------------
        # 13. Unusual DNS
        # ---------------------------------------------------------

        for i in range(100):
            event = make_event(
                db,
                log_type="dns",
                category="dns",
                action="unusual_dns",
                dst_port=53,
                details={
                    "query": f"very-long-suspicious-subdomain{i}.example.com",
                },
                raw="DNS anomaly detected",
                timestamp=now - timedelta(seconds=i % 60),
            )

            created_event_ids.append(event.event_id)

        db.commit()

        print(f"Inserted {len(created_event_ids)} replay events.")

        # ---------------------------------------------------------
        # Run detection
        # ---------------------------------------------------------

        rules = load_rules()

        print(f"Loaded {len(rules)} rules.")

        alert_ids = run_detection(
            db=db,
            rules=rules,
        )

        created_alert_ids.extend(alert_ids)

        print()
        print("Detection finished.")
        print(f"Alert IDs returned: {alert_ids}")

        # ---------------------------------------------------------
        # Display resulting alerts
        # ---------------------------------------------------------

        alerts = (
            db.query(Alert)
            .filter(Alert.alert_id.in_(alert_ids))
            .order_by(Alert.alert_id)
            .all()
        )

        print()
        print("Detected alerts:")

        for alert in alerts:
            print(
                f"{alert.alert_id}: "
                f"{alert.rule_id} | "
                f"{alert.severity} | "
                f"count={alert.count} | "
                f"chain={alert.chain_id}"
            )

        # ---------------------------------------------------------
        # Check alert-event relationships
        # ---------------------------------------------------------

        links = (
            db.query(AlertEvent)
            .filter(AlertEvent.alert_id.in_(alert_ids))
            .count()
        )

        print()
        print(f"Alert-event links created: {links}")

        if not alerts:
            raise RuntimeError(
                "Replay test failed: no alerts were created."
            )

        if links == 0:
            raise RuntimeError(
                "Replay test failed: no alert-event links were created."
            )

        expected = {
            "WEB-SQLI-001", "WEB-LFI-001", "WEB-CMD-001", "WEB-XSS-001",
            "DNS-ANOMALY-001", "NET-PORTSCAN-001", "IDS-SIG-001", "SSH-BF-001",
            "WEB-BF-001", "WEB-SCAN-001", "WEB-FLOOD-001", "SSH-SUCCESS-001",
            "NET-OUTBOUND-001",
        }
        fired = {a.rule_id for a in alerts}
        missing = sorted(expected - fired)
        if missing:
            raise RuntimeError(f"Replay test failed: missing rules {missing}")

        print()
        print("REPLAY TEST PASSED")

    finally:

        # Remove test alert-event links first
        test_event_ids = set(created_event_ids)
        if test_event_ids:
            db.query(AlertEvent).filter(
                AlertEvent.event_id.in_(test_event_ids)
            ).delete(
                synchronize_session=False
            )
        if created_alert_ids:
            db.query(AlertEvent).filter(
                AlertEvent.alert_id.in_(created_alert_ids)
            ).delete(
                synchronize_session=False
            )

            db.query(Alert).filter(
                Alert.alert_id.in_(created_alert_ids)
            ).delete(
                synchronize_session=False
            )

        # Remove test events
        if created_event_ids:
            db.query(Event).filter(
                Event.event_id.in_(created_event_ids)
            ).delete(
                synchronize_session=False
            )

        db.commit()
        db.close()

        print("Replay test data cleaned up.")


if __name__ == "__main__":
    main()
