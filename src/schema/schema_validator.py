from jsonschema import Draft202012Validator, SchemaError
from src.core.errors import InvalidSchemaError, SchemaTooComplexError

UNSUPPORTED_FEATURES = (
    "$ref",
    "oneOf",
    "anyOf",
    "allOf",
    "if",
    "then",
    "else",
    "patternProperties",
    "$recursiveRef",
    "$dynamicRef",
)


def _has_recursive_ref(schema: dict, _seen: set[int] | None = None) -> bool:
    """Heuristik: dieselbe Schema-Dict-ID taucht transitiv wieder auf."""
    if _seen is None:
        _seen = set()
    if not isinstance(schema, dict):
        return False
    if id(schema) in _seen:
        return True
    _seen.add(id(schema))
    for value in schema.values():
        if isinstance(value, dict):
            if _has_recursive_ref(value, _seen):
                return True
        elif isinstance(value, list):
            for item in value:
                if _has_recursive_ref(item, _seen):
                    return True
    return False


def validate_schema(schema: dict) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise InvalidSchemaError(str(exc)) from exc


def reject_complex_features(schema: dict) -> None:
    """Hart-ablehnen, wenn das Schema Features nutzt, die der Parser nicht garantiert.

    Ziel: ARCS-Bridge bekommt nur Schemas, die zuverlässig extrahiert
    werden können. Details siehe `docs/schema_guidelines.md`.
    """
    if not isinstance(schema, dict):
        raise SchemaTooComplexError("schema is not an object")

    found: list[str] = []
    for feature in UNSUPPORTED_FEATURES:
        if feature in schema:
            found.append(feature)

    if "$ref" in found or "oneOf" in found or "anyOf" in found or "allOf" in found:
        # Diese Features können überall in der Tiefe auftreten — reicht als
        # Signal, dass das Schema zu komplex ist.
        raise SchemaTooComplexError(
            "schema uses unsupported features",
            [f for f in found if f in {"$ref", "oneOf", "anyOf", "allOf"}],
        )

    if _has_recursive_ref(schema):
        raise SchemaTooComplexError("schema is recursive", ["recursive_ref"])

    if found:
        # Top-level unsupported features ohne harten Abbruch signalisieren.
        # Wirft absichtlich nichts — `validate_schema` oben hat das schon
        # syntaktisch geprüft. Diese Liste ist für künftige Telemetrie.
        pass
