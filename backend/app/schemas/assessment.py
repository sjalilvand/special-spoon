from typing import Any

from pydantic import BaseModel, Field


class AssessmentCreate(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)


class AssessmentUpdate(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    expected_version: int | None = None


class ReviewDecision(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)
