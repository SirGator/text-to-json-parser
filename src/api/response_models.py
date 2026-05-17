from typing import Any

from pydantic import BaseModel, Field


class ErrorInfo(BaseModel):
    code: str
    message: str
    details: list[str] = Field(default_factory=list)


class GenerateJsonResponse(BaseModel):
    ok: bool
    data: dict[str, Any] | None = None
    error: ErrorInfo | None = None
