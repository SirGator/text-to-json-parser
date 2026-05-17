# core/errors.py
class Text2JsonError(Exception):
    code = "text2json_error"

    def __init__(self, message: str, details: list[str] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or []

class InvalidSchemaError(Text2JsonError):
    code = "invalid_schema"

class InvalidOutputError(Text2JsonError):
    code = "invalid_output"

class LLMError(Text2JsonError):
    code = "llm_error"