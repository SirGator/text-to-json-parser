import httpx
from src.core.config import OLLAMA_URL, OLLAMA_MODEL, REQUEST_TIMEOUT, TEMPERATURE
from src.core.errors import LLMError

async def call_llm(prompt: str, schema: dict) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": schema,
        "options": {
            "temperature": TEMPERATURE,
            "top_p": 0.1,
            "num_predict": 2048,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
    except Exception as exc:
        raise LLMError(f"LLM request failed: {exc}") from exc
