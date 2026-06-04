# core/config.py
import os

def _normalize_base_url(value: str) -> str:
    if value.startswith(("http://", "https://")):
        return value
    return f"http://{value}"


# --- Backend-Auswahl ------------------------------------------------------
# "ollama" (default) | "openai" | "echo"
# "echo" liefert deterministisch ein Stub-JSON und braucht keinen Provider.
LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama").lower()

# --- Ollama ---------------------------------------------------------------
OLLAMA_URL = _normalize_base_url(os.getenv("OLLAMA_URL", "127.0.0.1:11434"))
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b-instruct")

# --- OpenAI ---------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = _normalize_base_url(
    os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# --- Allgemein ------------------------------------------------------------
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "60"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "1"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0"))

