from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models.event import Event
from ..models.alert import Alert
from ..models.incident import Incident


router = APIRouter(
    prefix="/api",
    tags=["Stats"]
)


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

    return {
        "total_events": total_events,
        "total_alerts": total_alerts,
        "total_incidents": total_incidents,
        "alerts_by_severity": alerts_by_severity,
        "alerts_by_status": alerts_by_status,
        "incidents_by_severity": incidents_by_severity,
        "incidents_by_status": incidents_by_status,
    }
