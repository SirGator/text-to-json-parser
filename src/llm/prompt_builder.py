import json
from typing import Any


def _format_schema(schema: dict[str, Any], depth: int = 0, max_depth: int = 2) -> str:
    indent = "  " * depth
    schema_type = schema.get("type")

    lines: list[str] = []
    if schema_type:
        lines.append(f"{indent}- type: {schema_type}")

    description = schema.get("description")
    if description:
        lines.append(f"{indent}- description: {description}")

    if "const" in schema:
        lines.append(f"{indent}- const: {schema['const']}")

    if "enum" in schema:
        lines.append(f"{indent}- enum: {schema['enum']}")

    for key in ("minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems"):
        if key in schema:
            lines.append(f"{indent}- {key}: {schema[key]}")

    if "required" in schema:
        lines.append(f"{indent}- required: {schema['required']}")

    if "additionalProperties" in schema:
        lines.append(f"{indent}- additionalProperties: {schema['additionalProperties']}")

    properties = schema.get("properties")
    if isinstance(properties, dict) and depth < max_depth:
        lines.append(f"{indent}- properties:")
        for name, child in properties.items():
            child_lines = _format_schema(child if isinstance(child, dict) else {}, depth + 1, max_depth)
            if child_lines:
                lines.append(f"{indent}  - {name}:")
                lines.extend(child_lines.splitlines())
            else:
                lines.append(f"{indent}  - {name}")

    items = schema.get("items")
    if isinstance(items, dict) and depth < max_depth:
        lines.append(f"{indent}- items:")
        lines.extend(_format_schema(items, depth + 1, max_depth).splitlines())

    return "\n".join(lines)


def _stable_fallbacks() -> str:
    return "\n".join(
        [
            "- string -> \"\"",
            "- integer -> 0",
            "- number -> 0",
            "- boolean -> false",
            "- array -> []",
            "- object -> {}",
            "- null -> null",
        ]
    )


def _render_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{key}}}", value)
    return rendered


def build_prompt(
    text: str,
    schema: dict[str, Any],
    context: dict[str, Any] | None = None,
    rules: dict[str, Any] | None = None,
    validation_feedback: list[str] | None = None,
    attempt: int = 1,
    custom_prompt: str | None = None,
) -> str:
    context = context or {}
    rules = rules or {
        "relative_time_requires_now": True,
        "do_not_add_extra_keys": True,
        "preserve_original_text_when_uncertain": True,
        "normalize_when_safe": True,
    }

    schema_summary = _format_schema(schema)
    feedback_text = json.dumps(validation_feedback or [], ensure_ascii=False, indent=2)

    values = {
        "text": text,
        "schema": json.dumps(schema, ensure_ascii=False, indent=2),
        "context": json.dumps(context, ensure_ascii=False, indent=2),
        "rules": json.dumps(rules, ensure_ascii=False, indent=2),
        "validation_feedback": feedback_text,
        "attempt": str(attempt),
        "schema_summary": schema_summary or "- (keine Details)",
        "stable_fallbacks": _stable_fallbacks(),
    }

    api_payload = json.dumps(
        {
            "text": text,
            "schema": schema,
            "context": context,
            "rules": rules,
            "validation_feedback": validation_feedback or [],
            "attempt": attempt,
        },
        ensure_ascii=False,
        indent=2,
    )

    instruction_template = custom_prompt.strip() if custom_prompt else (
        "Verarbeite die API-Eingaben und gib genau ein JSON-Objekt zurück, das schema entspricht.\n\n"
        "API-EINGABEN:\n"
        "- text kommt direkt aus dem Request.\n"
        "- schema kommt direkt aus dem Request.\n"
        "- context kommt direkt aus dem Request.\n"
        "- rules kommt direkt aus dem Request oder aus den Default-Regeln.\n"
        "- validation_feedback kommt aus dem letzten Versuch.\n"
        "- attempt ist die aktuelle Wiederholung.\n"
    )

    instruction = _render_template(instruction_template, values)

    return f"""
Du bist ein externer JSON-Extractor.

AUFGABE:
{instruction}

OUTPUT-VERTRAG:
- Gib ausschließlich valides JSON zurück.
- Kein Markdown.
- Keine Erklärung.
- Keine Kommentare.
- Kein Text vor oder nach dem JSON.
- Keine zusätzlichen Schlüssel außerhalb des Schemas.
- Wenn Informationen fehlen, liefere den sichersten schema-validen Wert.
- Wenn ein Feld nicht sicher bestimmbar ist, bevorzuge konservative Werte statt Halluzinationen.
- Nutze die folgenden Fallbacks nur, wenn das Schema sonst nicht erfüllt werden kann:

{values['stable_fallbacks']}

SCHEMA-ZUSAMMENFASSUNG:
{values['schema_summary']}

ZEIT-REGELN:
- Relative Zeiten wie "morgen", "später", "nächste Woche" dürfen nur mit context.now und context.timezone normalisiert werden.
- Wenn context.now oder context.timezone fehlen, darfst du relative Zeiten nicht erfinden.
- Behalte den Originaltext, wenn die Normalisierung unsicher ist.
- Schreibe normalisierte Werte nur dann, wenn sie belastbar ableitbar sind.

EXTRAKTIONS-REGELN:
- Verwende nur Informationen aus dem Input und dem Kontext.
- Erfinde keine neuen Entitäten, Werte oder Beziehungen.
- Wenn mehrere Werte möglich sind, nimm den im Text am klarsten gestützten Wert.
- Halte dich eng an enums, const, required und additionalProperties.

VALIDIERUNGSFEEDBACK VOM VORHERIGEN VERSUCH:
{values['validation_feedback']}

INPUT:
{api_payload}

GIB NUR DAS JSON-OBJEKT ZURÜCK.
""".strip()
