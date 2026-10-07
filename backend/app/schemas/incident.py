from datetime import datetime

from pydantic import BaseModel, Field


class IncidentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    severity: str = Field(min_length=1, max_length=20)
    category: str | None = Field(default=None, max_length=100)
    assigned_to: int | None = None
    affected_hosts: list[str] | None = None
    source_ips: list[str] | None = None


class IncidentResponse(BaseModel):
    incident_id: int
    incident_code: str
    title: str
    description: str | None
    severity: str
    status: str
    category: str | None
    assigned_to: int | None
    affected_hosts: list | None
    source_ips: list | None
    created_at: datetime
    closed_at: datetime | None
    root_cause: str | None
    lessons_learned: str | None


class IncidentStatusUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=30)
    comment: str = Field(min_length=1)


class NoteCreate(BaseModel):
    body: str = Field(min_length=1)


class EvidenceCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    type: str = Field(min_length=1, max_length=100)
    sha256: str = Field(min_length=64, max_length=64)
    size_bytes: int = Field(ge=0)
    storage_path: str = Field(min_length=1, max_length=500)


class ActionCreate(BaseModel):
    action_type: str = Field(min_length=1, max_length=50)
    target: str = Field(min_length=1, max_length=255)
    reason: str = Field(min_length=1)
    result: str = Field(min_length=1)
