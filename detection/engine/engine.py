from collections import defaultdict
from datetime import timedelta

from sqlalchemy.orm import Session

from backend.app.models.alert import Alert
from backend.app.models.alert_event import AlertEvent
from backend.app.models.event import Event

from .alert_manager import create_or_update_alert
from .evaluator import get_threshold_events, matches_rule


OPEN_STATUSES = {
    "open",
    "OPEN",
    "NEW",
    "INVESTIGATING",
}


def correlate_alerts(db: Session):
    alerts = (
        db.query(Alert)
        .filter(
            Alert.src_ip.isnot(None),
            Alert.last_seen.isnot(None),
        )
        .order_by(Alert.last_seen.asc())
        .all()
    )

    grouped = defaultdict(list)

    for alert in alerts:
        grouped[alert.src_ip].append(alert)

    next_chain_id = (
        db.query(Alert.chain_id)
        .filter(Alert.chain_id.isnot(None))
        .order_by(Alert.chain_id.desc())
        .first()
    )

    chain_id = (next_chain_id[0] + 1) if next_chain_id else 1

    for src_ip, source_alerts in grouped.items():

        for current_alert in source_alerts:

            window_start = (
                current_alert.last_seen
                - timedelta(minutes=30)
            )

            related_alerts = [
                alert
                for alert in source_alerts
                if (
                    window_start
                    <= alert.last_seen
                    <= current_alert.last_seen
                )
            ]

            categories = set()

            for alert in related_alerts:
                cat = getattr(alert, "category", None)
                if cat:
                    categories.add(str(cat))
                    continue
                rule_id = alert.rule_id
                if rule_id.startswith("SSH"):
                    categories.add("authentication")
                elif rule_id.startswith("WEB"):
                    categories.add("web")
                elif rule_id.startswith("NET"):
                    categories.add("network")
                elif rule_id.startswith("DNS"):
                    categories.add("dns")
                elif rule_id.startswith("IDS"):
                    categories.add("ids")

            if len(categories) >= 2:

                existing_chain = next(
                    (
                        alert.chain_id
                        for alert in related_alerts
                        if alert.chain_id is not None
                    ),
                    None,
                )

                current_chain = existing_chain or chain_id

                for alert in related_alerts:
                    alert.chain_id = current_chain

                if existing_chain is None:
                    chain_id += 1

    db.commit()


def run_detection(db: Session, rules: list[dict]):
    alerts_created_or_updated = []

    # ---------------------------------------------------------
    # Determine the largest rule time window.
    #
    # We need enough context for threshold rules; also ensure
    # backfilled/unlinked events are evaluated.
    # ---------------------------------------------------------

    windows = [
        rule.get("threshold", {}).get("window_seconds", 0)
        for rule in rules
        if rule.get("threshold")
    ]

    max_window_seconds = max(windows, default=300)

    # Find events that are not yet linked to any alert
    linked_event_ids = set(
        row[0] for row in db.query(AlertEvent.event_id).all()
    )

    unlinked_events = (
        db.query(Event)
        .filter(~Event.event_id.in_(linked_event_ids) if linked_event_ids else True)
        .all()
    )

    if not unlinked_events:
        correlate_alerts(db)
        return []

    # Load context window around unlinked events
    if linked_event_ids:
        all_events = (
            db.query(Event)
            .order_by(Event.timestamp.asc())
            .all()
        )
    else:
        all_events = list(unlinked_events)

    # Ensure we have enough history for threshold rules
    if all_events:
        earliest_unlinked = min(e.timestamp for e in unlinked_events)
        cutoff = earliest_unlinked - timedelta(seconds=max_window_seconds)
        # Also include events after cutoff
        context_events = [e for e in all_events if e.timestamp >= cutoff]
    else:
        context_events = list(unlinked_events)

    events = context_events
    if not events:
        events = list(all_events)

    event_ids = [event.event_id for event in events]

    new_event_ids = {e.event_id for e in unlinked_events}

    new_events = [event for event in events if event.event_id in new_event_ids]

    # ---------------------------------------------------------
    # Evaluate every enabled rule.
    # ---------------------------------------------------------

    # Ensure SSH-BF-001 is evaluated before SSH-SUCCESS-001
    rules_sorted = sorted(rules, key=lambda r: (0 if r.get("id") == "SSH-BF-001" else 1 if r.get("id") == "SSH-SUCCESS-001" else 2))
    for rule in rules_sorted:

        threshold = rule.get("threshold")

        if threshold:

            # Threshold rules need the entire recent window.
            detected_events = get_threshold_events(
                events,
                rule,
            )

        else:

            detected_events = [
                event
                for event in new_events
                if matches_rule(event, rule)
            ]

        if not detected_events:
            continue

        # -----------------------------------------------------
        # Only trigger a threshold rule if at least one of the
        # events involved in the detection is new.
        # -----------------------------------------------------

        detected_event_ids = {
            event.event_id
            for event in detected_events
        }

        if not detected_event_ids.intersection(new_event_ids):
            continue

        # -----------------------------------------------------
        # Special case:
        # Successful SSH login after an open SSH brute-force
        # alert.
        # -----------------------------------------------------

        if rule["id"] == "SSH-SUCCESS-001":

            for event in new_events:

                if not matches_rule(event, rule):
                    continue

                previous_bruteforce = (
                    db.query(Alert)
                    .filter(
                        Alert.rule_id == "SSH-BF-001",
                        Alert.src_ip == event.src_ip,
                        Alert.status.in_(OPEN_STATUSES),
                        Alert.last_seen >= (
                            event.timestamp
                            - timedelta(minutes=30)
                        ),
                        Alert.last_seen <= event.timestamp,
                    )
                    .first()
                )

                if not previous_bruteforce:
                    continue

                # Prevent duplicate SSH success alerts for the
                # same triggering event.

                already_linked = (
                    db.query(AlertEvent)
                    .filter(
                        AlertEvent.event_id == event.event_id,
                        AlertEvent.alert_id.in_(
                            db.query(Alert.alert_id).filter(
                                Alert.rule_id == "SSH-SUCCESS-001"
                            )
                        ),
                    )
                    .first()
                )

                if already_linked:
                    continue

                alert = Alert(
                    rule_id=rule["id"],
                    title=rule["name"],
                    severity="CRITICAL",
                    status="NEW",
                    first_seen=event.timestamp,
                    last_seen=event.timestamp,
                    src_ip=event.src_ip,
                    dst_ip=event.dst_ip,
                    count=1,
                )

                db.add(alert)
                db.flush()

                db.add(
                    AlertEvent(
                        alert_id=alert.alert_id,
                        event_id=event.event_id,
                    )
                )

                db.commit()

                alerts_created_or_updated.append(
                    alert.alert_id
                )

            continue

        # -----------------------------------------------------
        # Create or update normal alert.
        # -----------------------------------------------------

        alert = create_or_update_alert(
            db=db,
            rule=rule,
            events=detected_events,
        )

        if alert:
            alerts_created_or_updated.append(
                alert.alert_id
            )

    # ---------------------------------------------------------
    # Correlate alerts into attack chains.
    # ---------------------------------------------------------

    correlate_alerts(db)

    return alerts_created_or_updated
