from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class CustodyLog(Base):
    __tablename__ = "custody_log"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("evidence.id"),
        nullable=False
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )
