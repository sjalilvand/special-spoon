import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AppointmentCreate(BaseModel):
    case_id: uuid.UUID
    counselor_id: uuid.UUID | None = None
    scheduled_at: datetime
    duration_minutes: int | None = Field(default=None, ge=5, le=480)
    location: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=500)


class AppointmentUpdate(BaseModel):
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=480)
    location: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, pattern="^(done|cancelled|no_show)$")


class SessionCreate(BaseModel):
    occurred_at: datetime
    appointment_id: uuid.UUID | None = None
    content: dict[str, Any] = Field(default_factory=dict)


class SessionNoteUpdate(BaseModel):
    content: dict[str, Any] = Field(default_factory=dict)
    expected_version: int | None = None
