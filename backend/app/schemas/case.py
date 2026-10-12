import uuid

from pydantic import BaseModel, Field


class CaseCreate(BaseModel):
    applicant_id: uuid.UUID
    service_location_id: uuid.UUID | None = None
    service_type: str | None = Field(default=None, max_length=100)
    priority: str = Field(default="normal", pattern="^(low|normal|high)$")
    counselor_id: uuid.UUID | None = None
    assignment_reason: str | None = Field(default=None, max_length=500)


class CaseUpdate(BaseModel):
    expected_version: int
    service_type: str | None = Field(default=None, max_length=100)
    priority: str | None = Field(default=None, pattern="^(low|normal|high)$")
    service_location_id: uuid.UUID | None = None
    status: str | None = Field(default=None, pattern="^(active|suspended)$")


class AssignmentCreate(BaseModel):
    counselor_id: uuid.UUID
    reason: str | None = Field(default=None, max_length=500)
    expected_version: int | None = None
    role_in_case: str = Field(default="primary", pattern="^(primary|collaborator)$")


class CaseActionRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class ConsentCreate(BaseModel):
    status: str = Field(pattern="^(granted|revoked)$")
    note: str | None = Field(default=None, max_length=1000)
