from typing import Any

from pydantic import BaseModel, Field


class AssessmentCreate(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    # کد فرم (RS-PS-01-01 / RS-PS-04-01 / RS-PS-08-01)؛
    # در نبود آن، فرم پیش‌فرض RS-PS-04-01 استفاده می‌شود (سازگاری با نسخه‌های قبل).
    form_code: str | None = Field(default=None, max_length=50)


class AssessmentUpdate(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    expected_version: int | None = None


class ReviewDecision(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)
