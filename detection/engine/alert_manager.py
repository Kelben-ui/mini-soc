from sqlalchemy.orm import Session

from backend.app.models.alert import Alert
from backend.app.models.alert_event import AlertEvent

OPEN_STATUSES = {"open", "OPEN", "NEW", "INVESTIGATING"}


def create_or_update_alert(db: Session, rule: dict, events: list):
    if not events:
        return None

    def value(event, field):
        if isinstance(event, dict):
            return event.get(field)
        return getattr(event, field, None)

    latest_event = max(
        events,
        key=lambda event: value(event, "timestamp")
    )

    rule_id = rule["id"]
    src_ip = value(latest_event, "src_ip")
    dst_ip = value(latest_event, "dst_ip")

    existing_alert = (
        db.query(Alert)
        .filter(
            Alert.rule_id == rule_id,
            Alert.src_ip == src_ip,
            Alert.dst_ip == dst_ip,
            Alert.status.in_(OPEN_STATUSES),
        )
        .first()
    )

    now = value(latest_event, "timestamp")

    if existing_alert:
        alert = existing_alert
    else:
        alert = Alert(
            rule_id=rule_id,
            title=rule["name"],
            severity=rule["severity"],
            status="NEW",
            first_seen=now,
            last_seen=now,
            src_ip=src_ip,
            dst_ip=dst_ip,
            count=0,
        )
        db.add(alert)
        db.flush()

    new_event_count = 0

    for event in events:
        event_id = value(event, "event_id")

        if not event_id:
            continue

        existing_link = (
            db.query(AlertEvent)
            .filter(
                AlertEvent.alert_id == alert.alert_id,
                AlertEvent.event_id == event_id,
            )
            .first()
        )

        if not existing_link:
            db.add(
                AlertEvent(
                    alert_id=alert.alert_id,
                    event_id=event_id,
                )
            )
            new_event_count += 1

    if new_event_count > 0:
        alert.count += new_event_count
        alert.last_seen = now

    db.commit()
    db.refresh(alert)

    return alert
