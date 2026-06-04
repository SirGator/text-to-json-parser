"""Tests für den text-to-json-parser.

Drei Test-Klassen:

1. `UnitTests` — brauchen keinen Provider, testen Schema/Pipeline-Mock/Errors.
2. `OllamaIntegrationTests` — schlagen echte Ollama-Calls. Werden mit
   `pytest.skip` übersprungen, wenn kein Ollama läuft. Mit
   `RUN_OLLAMA_TESTS=1` werden sie erzwungen.
3. `ApiEndpointTests` — fahren den Parser per `fastapi.testclient`
   und prüfen HTTP-Endpunkte (`/health`, `/schemas`, `/validate`).
"""

from __future__ import annotations

import asyncio
import json
import os
import unittest
from typing import Any

# `src/` als Paket importierbar machen.
import sys
from pathlib import Path

_PARSER_ROOT = Path(__file__).resolve().parents[1]
if str(_PARSER_ROOT) not in sys.path:
    sys.path.insert(0, str(_PARSER_ROOT))

from src.api.request_models import GenerateJsonRequest, PromptConfig
from src.api.response_models import GenerateJsonResponse
from src.core.errors import (
    InvalidOutputError,
    InvalidSchemaError,
    LLMAuthError,
    LLMResponseError,
    LLMTimeoutError,
    LLMUnreachableError,
    SchemaTooComplexError,
)
from src.llm.llm_client import _echo_response, call_llm, ping_backend
from src.pipeline.flow import _clean_llm_output
from src.schema.json_validator import validate_json
from src.schema.schema_registry import (
    INTERPRETATION_PROPOSAL_SCHEMA,
    default_schemas,
    get_schema,
)
from src.schema.schema_validator import reject_complex_features, validate_schema


# ---------------------------------------------------------------------------
# Unit-Tests (kein Provider nötig)
# ---------------------------------------------------------------------------


class SchemaValidatorTests(unittest.TestCase):
    def test_accepts_simple_schema(self) -> None:
        validate_schema({"type": "object", "properties": {"a": {"type": "string"}}})

    def test_rejects_invalid_schema(self) -> None:
        with self.assertRaises(InvalidSchemaError):
            validate_schema({"type": "not-a-real-type"})

    def test_rejects_recursive_ref(self) -> None:
        # Tiefe Rekursion: ein Objekt enthält sich selbst
        rec: dict[str, Any] = {"type": "object", "properties": {}}
        rec["properties"]["self"] = rec
        with self.assertRaises(SchemaTooComplexError):
            reject_complex_features(rec)

    def test_rejects_oneof_anyof_allof(self) -> None:
        with self.assertRaises(SchemaTooComplexError):
            reject_complex_features(
                {"oneOf": [{"type": "string"}, {"type": "integer"}]}
            )
        with self.assertRaises(SchemaTooComplexError):
            reject_complex_features(
                {"anyOf": [{"type": "string"}, {"type": "integer"}]}
            )
        with self.assertRaises(SchemaTooComplexError):
            reject_complex_features(
                {"allOf": [{"type": "object"}]}
            )

    def test_accepts_minimal_arcs_schema(self) -> None:
        # Das Default-Schema des ARCS-Workers muss akzeptiert werden.
        reject_complex_features(INTERPRETATION_PROPOSAL_SCHEMA)


class OutputCleanerTests(unittest.TestCase):
    def test_plain_json_unchanged(self) -> None:
        self.assertEqual(_clean_llm_output('{"a": 1}'), '{"a": 1}')

    def test_strips_markdown_fence(self) -> None:
        self.assertEqual(
            _clean_llm_output('```json\n{"a": 1}\n```').strip(),
            '{"a": 1}',
        )

    def test_extracts_json_from_prose(self) -> None:
        text = 'Hier ist die Antwort: {"a": 1}. Hoffe das hilft.'
        self.assertEqual(_clean_llm_output(text), '{"a": 1}')

    def test_handles_empty(self) -> None:
        self.assertEqual(_clean_llm_output(""), "")


class JsonValidatorTests(unittest.TestCase):
    def test_passes_valid(self) -> None:
        validate_json(
            {"name": "x", "age": 1},
            {
                "type": "object",
                "required": ["name", "age"],
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
            },
        )

    def test_raises_on_missing_required(self) -> None:
        with self.assertRaises(InvalidOutputError) as ctx:
            validate_json(
                {"name": "x"},
                {"type": "object", "required": ["name", "age"]},
            )
        self.assertIn("age", " ".join(ctx.exception.details))


class EchoBackendTests(unittest.TestCase):
    def test_echo_returns_arcs_proposal_for_arcs_schema(self) -> None:
        text = _echo_response("hi", INTERPRETATION_PROPOSAL_SCHEMA)
        obj = json.loads(text)
        self.assertEqual(obj["status"], "ok")
        self.assertIn("intent", obj)
        self.assertEqual(obj["intent"]["name"], "echo_intent")

    def test_echo_returns_object_for_plain_schema(self) -> None:
        text = _echo_response("hi", {"type": "object"})
        self.assertEqual(text, "{}")


class RequestModelTests(unittest.TestCase):
    def test_prompt_config_prompt_wins(self) -> None:
        req = GenerateJsonRequest(
            text="x",
            schema={"type": "object"},
            prompt="old",
            prompt_config=PromptConfig(prompt="new"),
        )
        self.assertEqual(req.effective_prompt(), "new")
        self.assertEqual(req.effective_mode(), "reliable")

    def test_legacy_prompt_used_when_no_prompt_config(self) -> None:
        req = GenerateJsonRequest(text="x", schema={"type": "object"}, prompt="p")
        self.assertEqual(req.effective_prompt(), "p")

    def test_mode_default(self) -> None:
        req = GenerateJsonRequest(text="x", schema={"type": "object"})
        self.assertEqual(req.effective_mode(), "reliable")

    def test_mode_fast(self) -> None:
        req = GenerateJsonRequest(
            text="x",
            schema={"type": "object"},
            prompt_config=PromptConfig(mode="fast"),
        )
        self.assertEqual(req.effective_mode(), "fast")


# ---------------------------------------------------------------------------
# Echte Ollama-Integration
# ---------------------------------------------------------------------------


def _ollama_reachable() -> bool:
    """Synchroner Wrapper für ping_backend (asyncio.run wäre hier umständlich)."""
    return asyncio.run(ping_backend("ollama"))


_OLLAMA_FORCED = os.getenv("RUN_OLLAMA_TESTS") == "1"


@unittest.skipUnless(
    _OLLAMA_FORCED or _ollama_reachable(),
    "Ollama nicht erreichbar. Setze RUN_OLLAMA_TESTS=1 zum Erzwingen.",
)
class OllamaIntegrationTests(unittest.TestCase):
    """Echte Calls gegen Ollama. Modell und URL kommen aus env."""

    MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b-instruct")
    URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

    def test_health_reports_ollama_reachable(self) -> None:
        self.assertTrue(_ollama_reachable())

    def test_extracts_simple_object(self) -> None:
        schema = {
            "type": "object",
            "required": ["name", "age", "city"],
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "city": {"type": "string"},
            },
        }
        raw = asyncio.run(
            call_llm(
                "Max Mustermann ist 32 Jahre alt und wohnt in Berlin.",
                schema,
                model=self.MODEL,
                timeout=120,
            )
        )
        # Cleaner toleriert Markdown-Hüllen.
        cleaned = _clean_llm_output(raw)
        data = json.loads(cleaned)
        validate_json(data, schema)
        self.assertEqual(data["name"], "Max Mustermann")
        self.assertEqual(data["age"], 32)
        self.assertEqual(data["city"], "Berlin")

    def test_extracts_arcs_proposal(self) -> None:
        raw = asyncio.run(
            call_llm(
                "bitte erstelle einen bericht als json ueber die letzten pruefergebnisse",
                INTERPRETATION_PROPOSAL_SCHEMA,
                model=self.MODEL,
                timeout=120,
            )
        )
        cleaned = _clean_llm_output(raw)
        data = json.loads(cleaned)
        validate_json(data, INTERPRETATION_PROPOSAL_SCHEMA)
        # Mindestens diese zwei Felder müssen gesetzt sein.
        self.assertIn("status", data)
        self.assertIn("intent", data)
        self.assertIn("name", data["intent"])


# ---------------------------------------------------------------------------
# HTTP-Endpoints (mit TestClient)
# ---------------------------------------------------------------------------


class ApiEndpointTests(unittest.TestCase):
    """Lädt die FastAPI-App und prüft /health, /schemas, /validate."""

    @classmethod
    def setUpClass(cls) -> None:
        # TestClient erst NACH allen Imports initialisieren.
        from fastapi.testclient import TestClient
        from main import app

        cls.client = TestClient(app)

    def test_health_endpoint(self) -> None:
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertIn("backend", body)
        self.assertIn("provider_reachable", body)

    def test_schemas_list(self) -> None:
        resp = self.client.get("/schemas")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertIn("arcs.interpretation_proposal.v1", body["schemas"])

    def test_schema_lookup(self) -> None:
        resp = self.client.get("/schemas/arcs.interpretation_proposal.v1")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["schema_id"], "arcs.interpretation_proposal.v1")
        self.assertIn("properties", body["schema"])

    def test_schema_lookup_unknown_returns_404(self) -> None:
        resp = self.client.get("/schemas/does.not.exist")
        self.assertEqual(resp.status_code, 404)

    def test_validate_accepts_conforming_data(self) -> None:
        resp = self.client.post(
            "/validate",
            json={
                "data": {"name": "x", "age": 1},
                "schema": {
                    "type": "object",
                    "required": ["name", "age"],
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                    },
                },
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])

    def test_validate_rejects_non_conforming(self) -> None:
        resp = self.client.post(
            "/validate",
            json={
                "data": {"name": "x"},
                "schema": {"type": "object", "required": ["name", "age"]},
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "invalid_output")

    def test_generate_json_with_echo_backend(self) -> None:
        # Echo-Backend liefert immer interpretation_proposal Stub-Daten
        # wenn das Schema das ARCS-Format ist.
        os.environ["LLM_BACKEND"] = "echo"
        try:
            from importlib import reload
            import src.core.config as cfg_module
            import src.llm.llm_client as llm_module
            reload(cfg_module)
            reload(llm_module)
            reload(__import__("src.pipeline.flow", fromlist=["flow"]))
            from fastapi.testclient import TestClient
            from main import app
            client = TestClient(app)
            resp = client.post(
                "/generate-json",
                json={
                    "text": "hi",
                    "schema": INTERPRETATION_PROPOSAL_SCHEMA,
                },
            )
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertTrue(body["ok"])
            self.assertEqual(body["data"]["status"], "ok")
        finally:
            os.environ["LLM_BACKEND"] = "ollama"
            from importlib import reload
            import src.core.config as cfg_module
            import src.llm.llm_client as llm_module
            reload(cfg_module)
            reload(llm_module)
            reload(__import__("src.pipeline.flow", fromlist=["flow"]))

    def test_generate_json_rejects_complex_schema(self) -> None:
        os.environ["LLM_BACKEND"] = "echo"
        try:
            from importlib import reload
            import src.core.config as cfg_module
            import src.llm.llm_client as llm_module
            reload(cfg_module)
            reload(llm_module)
            reload(__import__("src.pipeline.flow", fromlist=["flow"]))
            from fastapi.testclient import TestClient
            from main import app
            client = TestClient(app)
            resp = client.post(
                "/generate-json",
                json={
                    "text": "hi",
                    "schema": {
                        "oneOf": [{"type": "string"}, {"type": "integer"}]
                    },
                },
            )
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertFalse(body["ok"])
            self.assertEqual(body["error"]["code"], "schema_too_complex")
        finally:
            os.environ["LLM_BACKEND"] = "ollama"
            from importlib import reload
            import src.core.config as cfg_module
            import src.llm.llm_client as llm_module
            reload(cfg_module)
            reload(llm_module)
            reload(__import__("src.pipeline.flow", fromlist=["flow"]))


if __name__ == "__main__":
    unittest.main()
