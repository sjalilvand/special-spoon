from pydantic import BaseModel, Field


class CommitRequest(BaseModel):
    duplicate_strategy: str = Field(default="skip", pattern="^(skip|update)$")
