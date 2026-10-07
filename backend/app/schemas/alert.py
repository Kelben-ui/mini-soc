from pydantic import BaseModel, Field


class AlertUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=30)
    assigned_to: int | None = None
    comment: str | None = None
    reason: str | None = None
