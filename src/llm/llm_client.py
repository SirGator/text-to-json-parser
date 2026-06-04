"""LLM-Client.

Unterstützt mehrere Backends:
- `ollama` (Default): lokales /api/generate, schema-gesteuert via `format`
- `openai`:           /v1/chat/completions, schema-gesteuert via `response_format`
- `echo`:             deterministischer Mock — für Tests ohne Provider

Jeder Request kann via `prompt_config` ein eigenes Modell, Temperatur und
top_p mitbringen. `model=None` oder fehlend fällt auf den
Umgebungs-Default zurück.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from src.core.errors import (
    LLMAuthError,
    LLMResponseError,
    LLMTimeoutError,
    LLMUnreachableError,
)
from src.core.config import (
    OLLAMA_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    LLM_BACKEND,
    REQUEST_TIMEOUT,
    TEMPERATURE,
)


def active_backend() -> str:
    """Welches Backend ist gerade konfiguriert?"""
    return LLM_BACKEND


def _default_model() -> str:
    backend = active_backend()
    if backend == "openai":
        return OPENAI_MODEL
    if backend == "echo":
        return "echo-1"
    return OLLAMA_MODEL


async def ping_backend(backend: str | None = None) -> bool:
    """True, wenn der Provider antwortet (für /health)."""
    backend = backend or active_backend()
    if backend == "echo":
        return True
    try:
        if backend == "openai":
            headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"} if OPENAI_API_KEY else {}
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{OPENAI_BASE_URL}/models", headers=headers)
                return resp.status_code < 500
        # ollama
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            return resp.status_code < 500
    except httpx.HTTPError:
        return False


# ---------------------------------------------------------------------------
# Öffentliche API
# ---------------------------------------------------------------------------


async def call_llm(
    prompt: str,
    schema: dict | None = None,
    *,
    model: str | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    timeout: float | None = None,
) -> str:
    """Provider-Call. Gibt den Rohtext der Antwort zurück."""
    backend = active_backend()
    model = model or _default_model()
    temperature = TEMPERATURE if temperature is None else temperature
    top_p = top_p if top_p is not None else 0.1
    timeout = timeout or REQUEST_TIMEOUT

    if backend == "echo":
        return _echo_response(prompt, schema)

    if backend == "openai":
        return await _call_openai(
            prompt=prompt,
            schema=schema,
            model=model,
            temperature=temperature,
            top_p=top_p,
            timeout=timeout,
        )

    return await _call_ollama(
        prompt=prompt,
        schema=schema,
        model=model,
        temperature=temperature,
        top_p=top_p,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------


def _echo_response(prompt: str, schema: dict | None) -> str:
    """Deterministisches Echo-Backend. Liefert schema-konformes Stub-JSON."""
    if not schema:
        return "{}"
    required = schema.get("required") or []
    props = schema.get("properties", {}) or {}
    if "intent" in required and props.get("intent", {}).get("type") == "object":
        return json.dumps(
            {
                "status": "ok",
                "intent": {
                    "name": "echo_intent",
                    "category": "echo",
                    "description": prompt[:200],
                },
                "confidence": 0.0,
                "slots": {},
                "missing_required_fields": [],
                "next_step": "execute",
            },
            ensure_ascii=False,
        )
    return "{}"


async def _call_ollama(
    *,
    prompt: str,
    schema: dict | None,
    model: str,
    temperature: float,
    top_p: float,
    timeout: float,
) -> str:
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": top_p,
            "num_predict": 2048,
        },
    }
    if schema:
        payload["format"] = schema

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
    except httpx.TimeoutException as exc:
        raise LLMTimeoutError(f"Ollama timeout after {timeout}s") from exc
    except httpx.HTTPError as exc:
        raise LLMUnreachableError(f"Ollama unreachable: {exc}") from exc

    if response.status_code in (401, 403):
        raise LLMAuthError(f"Ollama auth failed: HTTP {response.status_code}")
    if response.status_code >= 400:
        raise LLMResponseError(
            f"Ollama error HTTP {response.status_code}: {response.text[:300]}"
        )

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise LLMResponseError(f"Ollama response is not JSON: {exc}") from exc

    text = data.get("response", "")
    if not isinstance(text, str):
        raise LLMResponseError("Ollama response missing 'response' field")
    return text


async def _call_openai(
    *,
    prompt: str,
    schema: dict | None,
    model: str,
    temperature: float,
    top_p: float,
    timeout: float,
) -> str:
    if not OPENAI_API_KEY:
        raise LLMAuthError("OPENAI_API_KEY not configured")

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "top_p": top_p,
    }
    if schema:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "structured", "schema": schema, "strict": True},
        }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{OPENAI_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
    except httpx.TimeoutException as exc:
        raise LLMTimeoutError(f"OpenAI timeout after {timeout}s") from exc
    except httpx.HTTPError as exc:
        raise LLMUnreachableError(f"OpenAI unreachable: {exc}") from exc

    if response.status_code in (401, 403):
        raise LLMAuthError(f"OpenAI auth failed: HTTP {response.status_code}")
    if response.status_code >= 400:
        raise LLMResponseError(
            f"OpenAI error HTTP {response.status_code}: {response.text[:300]}"
        )

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise LLMResponseError(f"OpenAI response is not JSON: {exc}") from exc

    choices = data.get("choices") or []
    if not choices:
        raise LLMResponseError("OpenAI response has no choices")
    message = choices[0].get("message") or {}
    text = message.get("content")
    if not isinstance(text, str):
        raise LLMResponseError("OpenAI response missing 'content'")
    return text
