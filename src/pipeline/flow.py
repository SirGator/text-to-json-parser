"""Hauptpipeline: Request → Schema-Check → LLM → JSON-Validation → Response.

Drei Modi (siehe `Mode`):
- `fast`:      ein Versuch, kein Cleanup, sofortiger Fehler
- `reliable`:  bis zu MAX_RETRIES+1 Versuche, mit Validation-Feedback
- `strict`:    keine Markdown-/Kommentar-Strip, JSON muss 1:1 geliefert werden
"""

from __future__ import annotations

import json
from typing import Any

from src.api.request_models import GenerateJsonRequest
from src.api.response_models import GenerateJsonResponse, ErrorInfo
from src.core.config import MAX_RETRIES
from src.core.errors import (
    Text2JsonError,
    InvalidOutputError,
    LLMError,
)
from src.llm.prompt_builder import build_prompt
from src.llm.llm_client import call_llm, active_backend
from src.schema.schema_validator import validate_schema, reject_complex_features
from src.schema.json_validator import validate_json


# ---------------------------------------------------------------------------
# Output-Cleanup
# ---------------------------------------------------------------------------


def _clean_llm_output(raw: str) -> str:
    """Bereinigt typische LLM-Markdown-Hüllen und schneidet Vor- / Nachlauf ab.

    Bei `mode=strict` wird nichts verändert.
    """
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


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _format_validation_feedback(error: Exception) -> list[str]:
    if isinstance(error, InvalidOutputError):
        return [error.message, *error.details]
    return [str(error)]


def _max_attempts_for_mode(mode: str) -> int:
    if mode == "fast":
        return 1
    if mode == "strict":
        return max(1, MAX_RETRIES + 1)
    return max(1, MAX_RETRIES + 1)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


async def generate_json_flow(request: GenerateJsonRequest) -> GenerateJsonResponse:
    try:
        schema = request.schema_
        validate_schema(schema)
        reject_complex_features(schema)

        mode = request.effective_mode()
        attempts = _max_attempts_for_mode(mode)

        last_error: Text2JsonError | None = None
        validation_feedback: list[str] | None = None

        prompt_cfg = request.prompt_config
        custom_prompt = request.effective_prompt()
        rules = request.rules

        for attempt in range(1, attempts + 1):
            prompt = build_prompt(
                text=request.text,
                schema=schema,
                context=request.context,
                rules=rules,
                validation_feedback=validation_feedback,
                attempt=attempt,
                custom_prompt=custom_prompt,
            )

            try:
                raw = await call_llm(
                    prompt,
                    schema,
                    model=prompt_cfg.model if prompt_cfg else None,
                    temperature=prompt_cfg.temperature if prompt_cfg else None,
                    top_p=prompt_cfg.top_p if prompt_cfg else None,
                )
            except LLMError as exc:
                # Provider-Fehler sind sofort fatal — Retry hilft nicht.
                last_error = exc
                break

            cleaned = raw if mode == "strict" else _clean_llm_output(raw)

            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                last_error = InvalidOutputError(
                    f"Invalid JSON: {exc}", [cleaned[:200]]
                )
                validation_feedback = _format_validation_feedback(last_error)
                continue

            try:
                validate_json(data, schema)
            except InvalidOutputError as exc:
                last_error = exc
                validation_feedback = _format_validation_feedback(exc)
                continue

            return GenerateJsonResponse(ok=True, data=data)

        raise last_error or InvalidOutputError("Unknown output error")

    except Text2JsonError as exc:
        return GenerateJsonResponse(
            ok=False,
            error=ErrorInfo(
                code=exc.code,
                message=exc.message,
                details=exc.details,
            ),
        )


# ---------------------------------------------------------------------------
# Modul-Level Konstanten für Tests / externe Inspektion
# ---------------------------------------------------------------------------


PIPELINE_INFO: dict[str, Any] = {
    "backend": active_backend(),
    "max_retries": MAX_RETRIES,
    "modes": ["fast", "reliable", "strict"],
}
