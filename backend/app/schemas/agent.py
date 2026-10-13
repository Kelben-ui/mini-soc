from pydantic import BaseModel, Field


class IdsStatus(BaseModel):
    service: str | None = Field(default=None, max_length=100)
    status: str | None = Field(default=None, max_length=50)


class AgentHeartbeat(BaseModel):
    """Heartbeat posted by the log agent every ~30 s (task 3.7)."""

    name: str = Field(min_length=1, max_length=100)
    host: str | None = Field(default=None, max_length=255)
    status: str = Field(default="online", max_length=30)
    ids: IdsStatus | None = None
