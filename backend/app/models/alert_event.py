from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class AlertEvent(Base):
    __tablename__ = "alert_events"

    alert_id: Mapped[int] = mapped_column(
        ForeignKey("alerts.alert_id"),
        primary_key=True
    )

    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.event_id"),
        primary_key=True
    )
