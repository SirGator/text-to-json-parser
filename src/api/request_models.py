from typing import Any

from pydantic import BaseModel, Field


class GenerateJsonRequest(BaseModel):
    text: str = Field(min_length=1)
    schema_: dict[str, Any] = Field(alias="schema")
    context: dict[str, Any] | None = None
    prompt: str | None = None

    model_config = {
        "populate_by_name": True,
    }
