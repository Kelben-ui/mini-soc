from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.incident_id"),
        nullable=False
    )

    action_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    target: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    performed_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )

    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    result: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
