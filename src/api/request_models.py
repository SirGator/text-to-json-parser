from typing import Any, Literal

from pydantic import BaseModel, Field


# Erkennt der LLM-Provider strukturierte Outputs (Ollama `format` schema)?
# Wird vom Frontend / Worker benutzt, um das passende Code-Pfad zu wählen.
Mode = Literal["fast", "reliable", "strict"]


class PromptConfig(BaseModel):
    """Optionale Prompt- und Provider-Steuerung.

    Felder:
    - mode:           fast (1 Versuch), reliable (Retries), strict (kein Cleanup)
    - temperature:    wird an den Provider durchgereicht
    - top_p:          wird an den Provider durchgereicht
    - model:          überschreibt OLLAMA_MODEL nur für diesen Request
    - prompt:         vollständig eigener Prompt (Platzhalter siehe README)
    """

    mode: Mode = "reliable"
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    model: str | None = None
    prompt: str | None = None


class GenerateJsonRequest(BaseModel):
    text: str = Field(min_length=1)
    schema_: dict[str, Any] = Field(alias="schema")
    context: dict[str, Any] | None = None
    prompt: str | None = None  # legacy: vollständig eigener Prompt
    rules: dict[str, Any] | None = None
    prompt_config: PromptConfig | None = None

    model_config = {
        "populate_by_name": True,
    }

    def effective_prompt(self) -> str | None:
        """Welcher Custom-Prompt gewinnt? `prompt_config.prompt` schlägt `prompt`."""
        if self.prompt_config and self.prompt_config.prompt:
            return self.prompt_config.prompt
        return self.prompt

    def effective_mode(self) -> Mode:
        if self.prompt_config and self.prompt_config.mode:
            return self.prompt_config.mode
        return "reliable"
