from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from datetime import datetime, timedelta, timezone
import json

from ..database import get_db
from ..dependencies import get_current_user
from ..models.event import Event
from ..models.alert import Alert
from ..models.incident import Incident
from ..models.agent import Agent


router = APIRouter(
    prefix="/api",
    tags=["Stats"]
)

# An agent that has not sent a heartbeat within this window is "offline".
AGENT_ONLINE_WINDOW_SECONDS = 90


def _as_utc(value):
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value


def _agent_health(db):
    """Agent + IDS health for the Overview panel (task 3.7)."""
    now = datetime.now(timezone.utc)

    agents = []
    ids_status = "unknown"

    for agent in db.query(Agent).order_by(Agent.name).all():
        last = _as_utc(agent.last_heartbeat)

        online = bool(
            last
            and (now - last) <= timedelta(seconds=AGENT_ONLINE_WINDOW_SECONDS)
        )

        ids = {}

        if agent.details:
            try:
                stored = json.loads(agent.details)
                ids = stored.get("ids") or {}
            except ValueError:
                ids = {}

        if ids.get("status"):
            ids_status = ids["status"]

        agents.append(
            {
                "name": agent.name,
                "host": agent.host,
                "status": "online" if online else "offline",
                "last_heartbeat": last.isoformat() if last else None,
                "ids_status": ids.get("status"),
            }
        )

    return agents, ids_status


@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    total_events = db.query(
        func.count(Event.event_id)
    ).scalar()

    total_alerts = db.query(
        func.count(Alert.alert_id)
    ).scalar()

    total_incidents = db.query(
        func.count(Incident.incident_id)
    ).scalar()

    alerts_by_severity = dict(
        db.query(
            Alert.severity,
            func.count(Alert.alert_id)
        ).group_by(
            Alert.severity
        ).all()
    )

    alerts_by_status = dict(
        db.query(
            Alert.status,
            func.count(Alert.alert_id)
        ).group_by(
            Alert.status
        ).all()
    )

    incidents_by_severity = dict(
        db.query(
            Incident.severity,
            func.count(Incident.incident_id)
        ).group_by(
            Incident.severity
        ).all()
    )

    incidents_by_status = dict(
        db.query(
            Incident.status,
            func.count(Incident.incident_id)
        ).group_by(
            Incident.status
        ).all()
    )

    agents, ids_status = _agent_health(db)

    # --- Dashboard overview extras (task 7.4 / spec §15) -------------------

    now = datetime.now(timezone.utc)

    # Alerts per hour over the last 24 hours, as a Recharts-friendly series.
    buckets = {}

    for (last_seen,) in db.query(Alert.last_seen).filter(
        Alert.last_seen >= now - timedelta(hours=24)
    ).all():
        if last_seen is None:
            continue

        seen = _as_utc(last_seen)
        hour = seen.replace(minute=0, second=0, microsecond=0)
        buckets[hour] = buckets.get(hour, 0) + 1

    current_hour = now.replace(minute=0, second=0, microsecond=0)
    first_hour = current_hour - timedelta(hours=23)

    alerts_over_24h = []

    for i in range(24):
        hour = first_hour + timedelta(hours=i)
        alerts_over_24h.append(
            {"hour": hour.isoformat(), "count": buckets.get(hour, 0)}
        )

    top_source_ips = [
        {"src_ip": ip, "count": count}
        for ip, count in db.query(Alert.src_ip, func.count(Alert.alert_id))
        .filter(Alert.src_ip.isnot(None))
        .group_by(Alert.src_ip)
        .order_by(func.count(Alert.alert_id).desc())
        .limit(5)
        .all()
    ]

    top_attack_types = [
        {"type": attack_type, "count": count}
        for attack_type, count in db.query(Alert.category, func.count(Alert.alert_id))
        .filter(Alert.category.isnot(None))
        .group_by(Alert.category)
        .order_by(func.count(Alert.alert_id).desc())
        .limit(5)
        .all()
    ]

    open_incidents = db.query(
        func.count(Incident.incident_id)
    ).filter(
        func.lower(Incident.status).in_(("open", "investigating", "contained"))
    ).scalar()

    return {
        "total_events": total_events,
        "total_alerts": total_alerts,
        "total_incidents": total_incidents,
        "open_incidents": open_incidents or 0,
        "alerts_by_severity": alerts_by_severity,
        "alerts_by_status": alerts_by_status,
        "incidents_by_severity": incidents_by_severity,
        "incidents_by_status": incidents_by_status,
        "alerts_over_24h": alerts_over_24h,
        "top_source_ips": top_source_ips,
        "top_attack_types": top_attack_types,
        "agents": agents,
        "agents_online": sum(1 for a in agents if a["status"] == "online"),
        "ids_status": ids_status,
    }
