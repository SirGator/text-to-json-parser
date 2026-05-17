from jsonschema import Draft202012Validator
from src.core.errors import InvalidOutputError

def validate_json(data: dict, schema: dict) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: e.path)

    if errors:
        details = [
            f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in errors
        ]
        raise InvalidOutputError("Generated JSON does not match schema", details)
