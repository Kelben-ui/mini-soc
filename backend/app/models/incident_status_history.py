from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class IncidentStatusHistory(Base):
    __tablename__ = "incident_status_history"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.incident_id"),
        nullable=False
    )

    old_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    new_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    changed_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )

    comment: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
