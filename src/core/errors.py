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
    """Allgemeiner Provider-Fehler. Subklassen sind konkreter."""

    code = "llm_error"


class LLMUnreachableError(LLMError):
    code = "llm_unreachable"


class LLMTimeoutError(LLMError):
    code = "llm_timeout"


class LLMAuthError(LLMError):
    code = "llm_auth"


class LLMResponseError(LLMError):
    """Provider hat geantwortet, aber das Format ist unbrauchbar."""

    code = "llm_response"


class SchemaTooComplexError(InvalidSchemaError):
    """Hart-abgelehnt: Schema nutzt Features, die der Parser nicht unterstützt."""

    code = "schema_too_complex"