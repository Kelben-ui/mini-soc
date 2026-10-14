from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.event import Event
from ..dependencies import get_current_user


router = APIRouter(
    prefix="/api",
    tags=["Events"]
)


@router.get("/events")
def get_events(
    src_ip: str | None = Query(default=None),
    host: str | None = Query(default=None),
    log_type: str | None = Query(default=None),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    query = db.query(Event)

    if src_ip:
        query = query.filter(Event.src_ip == src_ip)

    if host:
        query = query.filter(Event.host == host)

    if log_type:
        query = query.filter(Event.log_type == log_type)

    if start_time:
        query = query.filter(Event.timestamp >= start_time)

    if end_time:
        query = query.filter(Event.timestamp <= end_time)

    total = query.count()

    events = (
        query.order_by(Event.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "items": [
            {
                "event_id": event.event_id,
                "timestamp": event.timestamp,
                "host": event.host,
                "log_type": event.log_type,
                "category": event.category,
                "action": event.action,
                "src_ip": event.src_ip,
                "src_port": event.src_port,
                "dst_ip": event.dst_ip,
                "dst_port": event.dst_port,
                "user": event.user,
                "outcome": event.outcome,
                "details": event.details,
                "raw": event.raw,
            }
            for event in events
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
