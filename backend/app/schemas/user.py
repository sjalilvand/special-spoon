from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    mobile: str | None = Field(default=None, max_length=20)
    roles: list[str] = Field(default_factory=list)


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    mobile: str | None = Field(default=None, max_length=20)
    status: str | None = Field(default=None, max_length=30)


class RolesUpdate(BaseModel):
    roles: list[str]


class ActivationTokenOut(BaseModel):
    token: str
    expires_at: datetime
