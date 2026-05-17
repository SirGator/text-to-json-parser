# Semantic JSON Engine

Ziel: beliebiger Text + beliebiges semantisch beschreibbares JSON-Schema -> zuverlässiges JSON, partial result oder Rückfrage.

## 1. Pipeline

```text
REQUEST
  text
  task
  schema
  mode: fast | reliable | strict
  options

↓
1. Input Guard
↓
2. Schema Guard
↓
3. Schema Summary
↓
4. Example Retrieval / Embeddings
↓
5. Text Decomposition
↓
6. Field Candidate Extraction
↓
7. Schema Mapping
↓
8. Constrained JSON Generation
↓
9. JSON Schema Validation
↓
10. Omission Check
↓
11. Hallucination Check
↓
12. Semantic Consistency Check
↓
13. Repair Pass
↓
14. Decision Layer
↓
RESPONSE
  parsed | partial | needs_clarification | unknown | failed
```

## 2. Was Jeder Schritt Macht

### 1. Input Guard

Prüft den Input:

- Text vorhanden?
- Text zu lang?
- Sprache erkannt?
- Enthält mehrere Aufgaben?
- Enthält riskante Aktion?

Internes Ergebnis:

```json
{
  "ok": true,
  "language": "de",
  "input_type": "command",
  "risk_signals": []
}
```

### 2. Schema Guard

Prüft das Ziel-Schema:

- gültiges JSON Schema?
- nicht zu groß?
- nicht zu tief?
- keine gefährlichen Features?
- Feldnamen/Descriptions verständlich?

Erlaubte MVP-Features:

- `type`
- `properties`
- `required`
- `enum`
- `items`
- `description`
- `additionalProperties`
- `minimum` / `maximum`
- `minLength` / `maxLength`
- `minItems` / `maxItems`

Erstmal begrenzen/blockieren:

- `$ref`
- recursive schemas
- `oneOf` / `anyOf` / `allOf`
- `if` / `then` / `else`
- `patternProperties`

### 3. Schema Summary

Aus dem Schema wird eine verständliche Beschreibung gebaut.

Beispiel:

Das Ziel-JSON erwartet:
- `device`: Das betroffene Gerät. Typ string.
- `room`: Raum der Aktion. Typ string.
- `state`: Zielzustand. Enum: `on`, `off`, `unknown`.
Pflichtfelder: `device`, `room`, `state`.
Keine zusätzlichen Felder erlaubt.

### 4. Example Retrieval / Embeddings

Du speicherst gute Beispiele und suchst ähnliche Fälle.

Query:

`task + text + schema_summary`

Beispiel gefundener Fall:

```json
{
  "text": "Mach nicht das Wohnzimmerlicht an, sondern die Küche.",
  "output": {
    "device": "light",
    "room": "Küche",
    "state": "on"
  },
  "tags": ["negation", "correction", "smart_home"]
}
```

### 5. Text Decomposition

Text wird zuerst in Bedeutung zerlegt, noch nicht ins Ziel-Schema.

Input:

`Mach nicht das Wohnzimmerlicht an, sondern das Licht in der Küche.`

Interne Analyse:

```json
{
  "utterance_type": "command",
  "main_intent": "set_device_state",
  "actions": [
    {
      "action": "turn_on",
      "target": "Wohnzimmerlicht",
      "negated": true,
      "evidence": "nicht das Wohnzimmerlicht an"
    },
    {
      "action": "turn_on",
      "target": "Licht in der Küche",
      "negated": false,
      "evidence": "sondern das Licht in der Küche"
    }
  ],
  "entities": [
    {
      "type": "device",
      "value": "Licht",
      "normalized": "light",
      "confidence": 0.98,
      "evidence": "Licht"
    },
    {
      "type": "room",
      "value": "Wohnzimmer",
      "negated": true,
      "confidence": 0.97,
      "evidence": "nicht das Wohnzimmerlicht"
    },
    {
      "type": "room",
      "value": "Küche",
      "negated": false,
      "confidence": 0.98,
      "evidence": "in der Küche"
    }
  ],
  "corrections": [
    {
      "from": "Wohnzimmerlicht",
      "to": "Licht in der Küche",
      "evidence": "nicht ... sondern ..."
    }
  ],
  "missing_information": [],
  "ambiguities": [],
  "confidence": 0.95
}
```

### 6. Field Candidate Extraction

Für jedes Zielfeld werden Kandidaten gebildet.

```json
{
  "field_candidates": {
    "device": [
      {
        "value": "light",
        "status": "supported",
        "evidence": "Licht",
        "confidence": 0.98
      }
    ],
    "room": [
      {
        "value": "Küche",
        "status": "supported",
        "evidence": "sondern das Licht in der Küche",
        "confidence": 0.98
      },
      {
        "value": "Wohnzimmer",
        "status": "contradicted",
        "evidence": "nicht das Wohnzimmerlicht",
        "confidence": 0.97
      }
    ],
    "state": [
      {
        "value": "on",
        "status": "supported",
        "evidence": "an",
        "confidence": 0.96
      }
    ]
  }
}
```

Status:

- `supported`
- `inferred`
- `defaulted`
- `missing`
- `ambiguous`
- `contradicted`

### 7. Schema Mapping

Kandidaten werden auf das Ziel-Schema gemappt.

Regeln:

- `supported` > `inferred` > `defaulted`
- `contradicted` niemals übernehmen
- `missing` nicht erfinden
- `ambiguous` nur übernehmen, wenn Confidence hoch genug

Output:

```json
{
  "device": "light",
  "room": "Küche",
  "state": "on"
}
```

### 8. Constrained JSON Generation

Das Modell darf nur JSON erzeugen, das zur Struktur passt.

Möglichkeiten:

- JSON Schema constrained decoding
- grammar decoding
- function calling / structured outputs

Das verhindert:

- kaputtes JSON
- falsche Typen
- ungültige Enums
- zusätzliche Felder

### 9. JSON Schema Validation

Dann nochmal hart validieren:

- `jsonschema`
- `fastjsonschema`
- `pydantic`

Wenn ungültig:

- Repair Pass
- nochmal validieren
- wenn wieder falsch -> `failed`

### 10. Omission Check

Prüft:

Wurde etwas Wichtiges aus dem Text ausgelassen, obwohl das Schema dafür ein Feld hat?

Beispiel:

Die Rede war emotional, klar, aber zu lang und am Ende verwirrend.

Schlechtes JSON:

```json
{
  "positive": ["emotional"],
  "negative": ["zu lang"]
}
```

Omission:

```json
{
  "omissions": [
    {
      "text": "klar",
      "should_map_to": "positive"
    },
    {
      "text": "am Ende verwirrend",
      "should_map_to": "negative"
    }
  ]
}
```

### 11. Hallucination Check

Prüft:

Hat das JSON etwas erfunden, das nicht im Text steht und nicht erlaubt abgeleitet wurde?

Beispiel:

```json
{
  "suggestions": ["mehr Bilder verwenden"]
}
```

Wenn das nicht im Text steht und Empfehlungen nicht gefragt sind:

```json
{
  "hallucinations": [
    {
      "field": "suggestions",
      "value": "mehr Bilder verwenden",
      "reason": "Nicht aus dem Text ableitbar."
    }
  ]
}
```

### 12. Semantic Consistency Check

Prüft:

Passt das finale JSON vollständig und widerspruchsfrei zum Originaltext?

Beispiel Fehler:

Text: `Mach das Licht aus`

JSON: `{"state": "on"}`

Check:

```json
{
  "valid": false,
  "issues": [
    {
      "field": "state",
      "actual": "on",
      "expected": "off",
      "reason": "Der Text sagt 'aus'."
    }
  ]
}
```

### 13. Repair Pass

Wenn Fehler gefunden wurden:

- Originaltext
- Schema
- aktuelles JSON
- Validation Errors
- Omissions
- Hallucinations
- Semantic Issues

-> repariertes JSON

Maximal 1-2 Versuche.

### 14. Decision Layer

Entscheidet final:

- `parsed`: alles ok
- `partial`: einige Felder sicher, andere fehlen
- `needs_clarification`: Pflichtfeld fehlt oder mehrere Interpretationen möglich
- `unknown`: keine klare Absicht
- `failed`: technisch/strukturell nicht lösbar

## 3. Final Response Format

### Erfolgreich

```json
{
  "ok": true,
  "status": "parsed",
  "data": {
    "device": "light",
    "room": "Küche",
    "state": "on"
  },
  "reliability": {
    "confidence": 0.96,
    "schema_validation": "passed",
    "semantic_check": "passed",
    "omissions": [],
    "hallucinations": [],
    "warnings": []
  }
}
```

### Teilweise

```json
{
  "ok": false,
  "status": "needs_clarification",
  "partial_data": {
    "device": "light",
    "state": "on"
  },
  "missing": ["room"],
  "question": "In welchem Raum soll das Licht eingeschaltet werden?",
  "reliability": {
    "confidence": 0.76,
    "schema_validation": "partial",
    "semantic_check": "passed",
    "warnings": ["Der Raum wurde nicht genannt."]
  }
}
```

## 4. Python-Ordnerstruktur

```text
semantic_json_engine/
├─ app/
│  ├─ main.py
│  ├─ routes/
│  │  ├─ interpret.py
│  │  ├─ health.py
│  │  └─ schemas.py
│  └─ middleware/
│     ├─ error_handler.py
│     ├─ request_id.py
│     └─ rate_limit.py
│
├─ pipeline/
│  ├─ interpret_pipeline.py
│  ├─ fast_pipeline.py
│  ├─ reliable_pipeline.py
│  ├─ strict_pipeline.py
│  └─ types.py
│
├─ guards/
│  ├─ input_guard.py
│  ├─ schema_guard.py
│  ├─ risk_guard.py
│  └─ types.py
│
├─ schema/
│  ├─ summary.py
│  ├─ fingerprint.py
│  ├─ quality.py
│  ├─ normalizer.py
│  └─ types.py
│
├─ llm/
│  ├─ client.py
│  ├─ types.py
│  ├─ providers/
│  │  ├─ ollama.py
│  │  ├─ openai_compatible.py
│  │  ├─ vllm.py
│  │  └─ mock.py
│  └─ prompts/
│     ├─ decompose.py
│     ├─ field_candidates.py
│     ├─ map_to_schema.py
│     ├─ repair.py
│     ├─ omission_check.py
│     ├─ hallucination_check.py
│     └─ semantic_check.py
│
├─ decomposition/
│  ├─ decompose_text.py
│  ├─ field_candidates.py
│  └─ types.py
│
├─ mapping/
│  ├─ map_to_schema.py
│  ├─ constrained_generation.py
│  └─ types.py
│
├─ validation/
│  ├─ json_schema_validator.py
│  ├─ output_validator.py
│  └─ types.py
│
├─ checks/
│  ├─ omission.py
│  ├─ hallucination.py
│  ├─ semantic_consistency.py
│  ├─ contradiction.py
│  └─ types.py
│
├─ repair/
│  ├─ repair_output.py
│  ├─ repair_policy.py
│  └─ types.py
│
├─ retrieval/
│  ├─ embeddings.py
│  ├─ example_retriever.py
│  ├─ schema_retriever.py
│  ├─ vector_store.py
│  └─ types.py
│
├─ reliability/
│  ├─ confidence.py
│  ├─ field_status.py
│  ├─ decision.py
│  └─ types.py
│
├─ policies/
│  ├─ action_policy.py
│  ├─ risk_policy.py
│  ├─ confirmation_policy.py
│  └─ types.py
│
├─ storage/
│  ├─ db.py
│  ├─ repositories/
│  │  ├─ interpretation_repository.py
│  │  ├─ schema_repository.py
│  │  └─ example_repository.py
│  └─ migrations/
│
├─ observability/
│  ├─ logger.py
│  ├─ metrics.py
│  ├─ tracing.py
│  └─ audit_log.py
│
├─ config/
│  ├─ settings.py
│  ├─ models.py
│  ├─ thresholds.py
│  └─ modes.py
│
├─ shared/
│  ├─ errors.py
│  ├─ result.py
│  ├─ ids.py
│  ├─ json_utils.py
│  └─ time.py
│
├─ tests/
│  ├─ unit/
│  │  ├─ test_schema_guard.py
│  │  ├─ test_schema_summary.py
│  │  ├─ test_output_validator.py
│  │  └─ test_decision.py
│  ├─ integration/
│  │  ├─ test_fast_pipeline.py
│  │  ├─ test_reliable_pipeline.py
│  │  └─ test_strict_pipeline.py
│  └─ fixtures/
│     ├─ smart_home/
│     │  ├─ simple.json
│     │  ├─ negation.json
│     │  └─ ambiguity.json
│     ├─ speech_feedback/
│     │  ├─ mixed_sentiment.json
│     │  └─ omissions.json
│     └─ schemas/
│        ├─ smart_home.schema.json
│        ├─ sentiment.schema.json
│        └─ bad_schema.schema.json
│
├─ data/
│  ├─ examples/
│  │  ├─ smart_home.examples.jsonl
│  │  ├─ sentiment.examples.jsonl
│  │  └─ generic.examples.jsonl
│  ├─ schemas/
│  │  └─ registry.json
│  └─ evals/
│     ├─ negation.eval.jsonl
│     ├─ hallucination.eval.jsonl
│     ├─ omission.eval.jsonl
│     └─ schema_mapping.eval.jsonl
│
├─ scripts/
│  ├─ seed_examples.py
│  ├─ run_evals.py
│  ├─ benchmark_models.py
│  └─ generate_schema_summary.py
│
├─ docs/
│  ├─ architecture.md
│  ├─ pipeline.md
│  ├─ api.md
│  ├─ reliability.md
│  └─ schema_guidelines.md
│
├─ docker/
│  ├─ Dockerfile
│  ├─ docker-compose.yml
│  └─ qdrant.yml
│
├─ pyproject.toml
├─ .env.example
└─ README.md
```

## 5. Wichtigste Datei: `interpret_pipeline.py`

```python
async def interpret_pipeline(request: InterpretRequest) -> InterpretResponse:
    input_result = input_guard(request)

    if not input_result.ok:
        return failed_response(input_result.error)

    schema_result = schema_guard(request.schema)

    if not schema_result.ok:
        return failed_response(schema_result.error)

    schema_summary = build_schema_summary(request.schema)

    examples = await retrieve_examples(
        text=request.text,
        task=request.task,
        schema_summary=schema_summary,
    )

    meaning = await decompose_text(
        text=request.text,
        task=request.task,
        examples=examples,
    )

    candidates = await extract_field_candidates(
        meaning=meaning,
        schema=request.schema,
        schema_summary=schema_summary,
    )

    output = await map_to_schema(
        text=request.text,
        task=request.task,
        schema=request.schema,
        schema_summary=schema_summary,
        meaning=meaning,
        candidates=candidates,
        examples=examples,
    )

    validation = validate_output(
        schema=request.schema,
        data=output,
    )

    if not validation.valid:
        output = await repair_output(
            text=request.text,
            schema=request.schema,
            output=output,
            validation_errors=validation.errors,
        )

        validation = validate_output(
            schema=request.schema,
            data=output,
        )

    if not validation.valid:
        return failed_response(
            code="OUTPUT_SCHEMA_VALIDATION_FAILED",
            details=validation.errors,
        )

    checks = await run_checks(
        text=request.text,
        schema=request.schema,
        schema_summary=schema_summary,
        output=output,
        meaning=meaning,
    )

    if not checks.valid:
        repaired = await repair_output(
            text=request.text,
            schema=request.schema,
            output=output,
            semantic_issues=checks.issues,
            omissions=checks.omissions,
            hallucinations=checks.hallucinations,
        )

        repaired_validation = validate_output(
            schema=request.schema,
            data=repaired,
        )

        if repaired_validation.valid:
            repaired_checks = await run_checks(
                text=request.text,
                schema=request.schema,
                schema_summary=schema_summary,
                output=repaired,
                meaning=meaning,
            )

            return decide_final_response(
                output=repaired,
                validation=repaired_validation,
                checks=repaired_checks,
                meaning=meaning,
            )

    return decide_final_response(
        output=output,
        validation=validation,
        checks=checks,
        meaning=meaning,
    )
```

## 6. Reihenfolge fürs Bauen

### Phase 1

- FastAPI Route
- Schema Guard
- Schema Summary
- LLM JSON Output
- JSON Schema Validation

### Phase 2

- Text Decomposition
- Field Candidates
- Semantic Check
- Repair Pass

### Phase 3

- Embeddings
- Example Retrieval
- Omission/Hallucination Checks

### Phase 4

- Strict Mode
- Risk Policies
- Evaluation Suite
- Model Benchmarks

## 7. Kernregel für die Engine

Fülle alles, was belegbar ist.
Markiere alles, was unsicher ist.
Erfinde nichts.
Lasse nichts Relevantes weg.
Frage nach, wenn ein Pflichtfeld fehlt.
