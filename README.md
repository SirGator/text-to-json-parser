# Text to JSON Parser

Eine kleine API, die Freitext, Kontext und ein JSON Schema entgegennimmt und daraus schema-konformes JSON erzeugt.

Wird vom **ARCS interpretation_worker** aufgerufen, um freien Text in
`arcs.interpretation_proposal.v1` zu übersetzen. Läuft eigenständig
als FastAPI-Service.

## Was es kann

- Extraktion von strukturierten Daten aus Freitext
- Validierung gegen ein JSON Schema
- Optionaler, eigener Prompt mit Platzhaltern
- Mehrere LLM-Backends (Ollama lokal, OpenAI, deterministisches `echo`)
- Eingebautes Schema `arcs.interpretation_proposal.v1` für ARCS
- Health- und Schema-Lookup-Endpoints für die ARCS-Bridge
- Einfache Web-UI im Browser

## API

### `POST /generate-json`

Request:

```json
{
  "text": "Max Mustermann ist 32 Jahre alt und wohnt in Berlin.",
  "schema": {
    "type": "object",
    "properties": {
      "name": { "type": "string" },
      "age": { "type": "integer" },
      "city": { "type": "string" }
    },
    "required": ["name", "age", "city"],
    "additionalProperties": false
  },
  "context": {
    "now": "2026-05-17T12:00:00Z",
    "timezone": "Europe/Berlin"
  },
  "prompt": "Extrahiere aus {text} nur name, age und city.",
  "prompt_config": {
    "mode": "reliable",
    "temperature": 0.0,
    "model": "qwen2.5:14b-instruct"
  },
  "rules": {
    "do_not_add_extra_keys": true
  }
}
```

Felder:

- `text` (required):  Freitext, der extrahiert werden soll
- `schema` (required): JSON Schema, gegen das geprüft wird
- `context` (optional): beliebige Kontext-Daten
- `prompt` (optional): Custom-Prompt mit Platzhaltern `{text}`, `{schema}`,
  `{context}`, `{rules}`, `{validation_feedback}`, `{attempt}`
- `prompt_config` (optional): siehe unten
- `rules` (optional): Extraktionsregeln, werden an den Prompt gerendert

`prompt_config`:

- `mode`: `fast` | `reliable` | `strict` (default `reliable`)
- `temperature`: float, optional, provider-spezifisch
- `top_p`: float, optional, provider-spezifisch
- `model`: string, überschreibt `OLLAMA_MODEL` / `OPENAI_MODEL`
- `prompt`: vollständig eigener Prompt (schlägt das Top-Level `prompt`-Feld)

Antwort bei Erfolg:

```json
{
  "ok": true,
  "data": { "name": "Max Mustermann", "age": 32, "city": "Berlin" },
  "error": null
}
```

Antwort bei Fehler:

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "invalid_output",
    "message": "Generated JSON does not match schema",
    "details": ["age: must be integer"]
  }
}
```

Fehler-Codes:

| Code | Bedeutung |
|------|-----------|
| `invalid_schema` | Schema ist kein gültiges JSON Schema |
| `schema_too_complex` | Schema nutzt `$ref`, `oneOf`, `anyOf`, `allOf` oder Rekursion |
| `invalid_output` | LLM-Output matched das Schema nicht |
| `llm_unreachable` | Provider nicht erreichbar |
| `llm_timeout` | Provider-Antwort hat zu lange gedauert |
| `llm_auth` | API-Key fehlt oder ist ungültig |
| `llm_response` | Provider hat in einem kaputten Format geantwortet |

### `GET /health`

Liefert Liveness, Readyness und Provider-Status.

```json
{
  "ok": true,
  "service": "text-to-json-parser",
  "version": "0.2.0",
  "backend": "ollama",
  "provider_reachable": true,
  "structured_output": true,
  "provider_error": null
}
```

### `GET /schemas`

Liste der eingebauten Schemas (z.B. `arcs.interpretation_proposal.v1`).

### `GET /schemas/{schema_id}`

Liefert das gewünschte Schema, oder 404 wenn unbekannt.

### `POST /validate`

Prüft `data` gegen `schema`. Nützlich für ARCS Smoke-Tests.

## UI

`GET /`

Die Web-UI bietet vier Felder:

1. Text
2. Schema
3. Prompt
4. JSON Output

## Starten

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Ollama (Default)
uvicorn main:app --host 127.0.0.1 --port 8000

# OpenAI
LLM_BACKEND=openai OPENAI_API_KEY=sk-... \
  uvicorn main:app --host 127.0.0.1 --port 8000
```

Danach `http://127.0.0.1:8000/` im Browser öffnen.

## Konfiguration

Alle Werte kommen aus Umgebungsvariablen:

| Variable | Default | Bedeutung |
|----------|---------|-----------|
| `LLM_BACKEND` | `ollama` | `ollama` \| `openai` \| `echo` |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama API |
| `OLLAMA_MODEL` | `qwen2.5:14b-instruct` | Default-Modell |
| `OPENAI_API_KEY` | (leer) | OpenAI Key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI Endpoint |
| `OPENAI_MODEL` | `gpt-4o-mini` | Default-Modell |
| `REQUEST_TIMEOUT` | `60` | HTTP-Timeout in Sekunden |
| `MAX_RETRIES` | `1` | Anzahl Retries (modus `reliable`) |
| `TEMPERATURE` | `0` | Default-Temperatur |

## Tests

```bash
# Unit + Endpoint-Tests (kein Provider nötig)
python -m unittest tests.test_parser

# Integration mit echtem Ollama
RUN_OLLAMA_TESTS=1 python -m unittest tests.test_parser
```

Die Integration-Tests werden automatisch übersprungen, wenn kein
Ollama läuft. Mit `RUN_OLLAMA_TESTS=1` werden sie erzwungen.
