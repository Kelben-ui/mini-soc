from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Alert(Base):
    __tablename__ = "alerts"

    alert_id: Mapped[int] = mapped_column(
        primary_key=True
    )

    rule_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False
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

    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    src_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True
    )

    dst_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True
    )

    count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1
    )

    chain_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    assigned_to: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True
    )

    incident_id: Mapped[int | None] = mapped_column(
        ForeignKey("incidents.incident_id"),
        nullable=True
    )
