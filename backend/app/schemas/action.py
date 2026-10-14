from pydantic import BaseModel, Field


class ActionExecutionRequest(BaseModel):
    """Body for confirming an IPS block/unblock (task 4.7).

    ``confirm`` must be ``True``: blocking is never automatic, every execution
    needs an explicit human confirmation (contracts 9.5).
    """

    confirm: bool = False
    reason: str | None = Field(default=None, max_length=500)
    timeout_seconds: int | None = Field(default=None, ge=60, le=604800)


class ActionUnblockRequest(BaseModel):
    confirm: bool = False
    reason: str | None = Field(default=None, max_length=500)
