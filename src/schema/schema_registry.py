"""Eingebaute Schemas, die der Parser ohne externe Quelle kennt.

Der ARCS interpretation_worker ruft /schemas/{schema_id} auf, um
beispielsweise das `arcs.interpretation_proposal.v1` Schema zu holen,
das ARCS Core als Erwartung an das Worker-Ergebnis mitschickt.
"""

from __future__ import annotations

from typing import Any


INTERPRETATION_PROPOSAL_SCHEMA: dict[str, Any] = {
    "$id": "arcs.interpretation_proposal.v1",
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ARCS Interpretation Proposal",
    "type": "object",
    "required": [
        "status",
        "intent",
        "confidence",
        "slots",
        "missing_required_fields",
        "next_step",
    ],
    "properties": {
        "status": {
            "type": "string",
            "enum": ["ok", "blocked", "needs_clarification"],
        },
        "intent": {
            "type": "object",
            "required": ["name", "category", "description"],
            "properties": {
                "name": {"type": "string"},
                "category": {"type": "string"},
                "description": {"type": "string"},
            },
            "additionalProperties": True,
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "slots": {"type": "object"},
        "missing_required_fields": {
            "type": "array",
            "items": {"type": "string"},
        },
        "next_step": {
            "type": "string",
            "enum": ["execute", "ask", "block"],
        },
    },
    "additionalProperties": True,
}


def default_schemas() -> dict[str, dict[str, Any]]:
    return {
        "arcs.interpretation_proposal.v1": INTERPRETATION_PROPOSAL_SCHEMA,
    }


def get_schema(schema_id: str) -> dict[str, Any] | None:
    return default_schemas().get(schema_id)
