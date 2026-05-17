from jsonschema import Draft202012Validator, SchemaError
from src.core.errors import InvalidSchemaError

def validate_schema(schema: dict) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise InvalidSchemaError(str(exc)) from exc
