from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Event(Base):
    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    host: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    log_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    src_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True
    )

    src_port: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    dst_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True
    )

    dst_port: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    user: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    outcome: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True
    )

    raw: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
