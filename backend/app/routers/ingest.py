from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import verify_ingest_api_key
from ..models.event import Event
from ..schemas.event import EventBatch

router = APIRouter(
    prefix="/api",
    tags=["Ingestion"]
)


@router.post("/ingest")
def ingest_events(
    batch: EventBatch,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_ingest_api_key)
):
    accepted = 0
    duplicates = 0

    for event_data in batch.events:
        existing_event = db.query(Event).filter(
            Event.event_id == event_data.event_id
        ).first()

        if existing_event:
            duplicates += 1
            continue

        event = Event(
            event_id=event_data.event_id,
            timestamp=event_data.timestamp,
            host=event_data.host,
            log_type=event_data.log_type,
            category=event_data.category,
            action=event_data.action,
            src_ip=event_data.src_ip,
            src_port=event_data.src_port,
            dst_ip=event_data.dst_ip,
            dst_port=event_data.dst_port,
            user=event_data.user,
            outcome=event_data.outcome,
            details=event_data.details,
            raw=event_data.raw,
        )

        db.add(event)
        accepted += 1

    db.commit()

    return {
        "message": "Events processed successfully",
        "accepted": accepted,
        "duplicates": duplicates,
    }
