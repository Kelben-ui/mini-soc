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

    return {
        "total_events": total_events,
        "total_alerts": total_alerts,
        "total_incidents": total_incidents,
        "alerts_by_severity": alerts_by_severity,
        "alerts_by_status": alerts_by_status,
        "incidents_by_severity": incidents_by_severity,
        "incidents_by_status": incidents_by_status,
        "agents": agents,
        "agents_online": sum(1 for a in agents if a["status"] == "online"),
        "ids_status": ids_status,
    }
