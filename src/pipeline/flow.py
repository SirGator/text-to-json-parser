import json
from typing import Any

from src.api.request_models import GenerateJsonRequest
from src.api.response_models import GenerateJsonResponse, ErrorInfo
from src.core.config import MAX_RETRIES
from src.core.errors import Text2JsonError, InvalidOutputError
from src.llm.prompt_builder import build_prompt
from src.llm.llm_client import call_llm
from src.schema.schema_validator import validate_schema
from src.schema.json_validator import validate_json


def _clean_llm_output(raw: str) -> str:
    text = raw.strip()

    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    if text.startswith("{") or text.startswith("["):
        return text

    start_candidates = [idx for idx in (text.find("{"), text.find("[")) if idx != -1]
    if not start_candidates:
        return text

    start = min(start_candidates)
    end = max(text.rfind("}"), text.rfind("]"))
    if end > start:
        return text[start : end + 1]

    return text


def _format_validation_feedback(error: Exception) -> list[str]:
    if isinstance(error, InvalidOutputError):
        return [error.message, *error.details]
    return [str(error)]

async def generate_json_flow(request: GenerateJsonRequest) -> GenerateJsonResponse:
    try:
        schema = request.schema_
        validate_schema(schema)

        last_error: Text2JsonError | None = None
        validation_feedback: list[str] | None = None

        for attempt in range(1, MAX_RETRIES + 2):
            prompt = build_prompt(
                text=request.text,
                schema=schema,
                context=request.context,
                validation_feedback=validation_feedback,
                attempt=attempt,
                custom_prompt=request.prompt,
            )
            raw = await call_llm(prompt, schema)

            try:
                data = json.loads(_clean_llm_output(raw))
                validate_json(data, schema)
                return GenerateJsonResponse(ok=True, data=data)
            except json.JSONDecodeError as exc:
                last_error = InvalidOutputError(f"Invalid JSON: {exc}")
                validation_feedback = _format_validation_feedback(last_error)
            except InvalidOutputError as exc:
                last_error = exc
                validation_feedback = _format_validation_feedback(exc)

        raise last_error or InvalidOutputError("Unknown output error")

    except Text2JsonError as exc:
        return GenerateJsonResponse(
            ok=False,
            error=ErrorInfo(
                code=exc.code,
                message=exc.message,
                details=exc.details
            )
        )
