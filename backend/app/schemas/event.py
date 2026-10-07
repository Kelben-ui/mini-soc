from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    event_id: str = Field(min_length=1, max_length=36)
    timestamp: datetime
    host: str = Field(min_length=1, max_length=255)
    log_type: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=100)
    action: str = Field(min_length=1, max_length=100)

    src_ip: str | None = Field(default=None, max_length=45)
    src_port: int | None = Field(default=None, ge=1, le=65535)

    dst_ip: str | None = Field(default=None, max_length=45)
    dst_port: int | None = Field(default=None, ge=1, le=65535)

    user: str | None = Field(default=None, max_length=255)
    outcome: str | None = Field(default=None, max_length=50)

    details: dict[str, Any] | None = None

    raw: str = Field(min_length=1)


class EventBatch(BaseModel):
    events: list[EventCreate] = Field(min_length=1)
