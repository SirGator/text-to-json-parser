# core/config.py
import os

def _normalize_base_url(value: str) -> str:
    if value.startswith(("http://", "https://")):
        return value
    return f"http://{value}"


OLLAMA_URL = _normalize_base_url(os.getenv("OLLAMA_URL", "127.0.0.1:11434"))
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b-instruct")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "60"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "1"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0"))

