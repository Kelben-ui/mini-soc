from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Incident(Base):
    __tablename__ = "incidents"

    incident_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    incident_code: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="open"
    )

    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    assigned_to: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    affected_hosts: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True
    )

    source_ips: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    contained_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    root_cause: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    lessons_learned: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
