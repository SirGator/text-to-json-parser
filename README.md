# Text to JSON Parser

Eine kleine API, die Freitext, Kontext und ein JSON Schema entgegennimmt und daraus schema-konformes JSON erzeugt.

## Was es kann

- Extraktion von strukturierten Daten aus Freitext
- Validierung gegen ein JSON Schema
- Optionaler, eigener Prompt mit Platzhaltern
- Einfache Web-UI im Browser

## API

`POST /generate-json`

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
  "prompt": "Extrahiere aus {text} nur name, age und city. Nutze das Schema: {schema}. Gib nur JSON zurueck."
}
```

Der `prompt` ist optional. Er kann Platzhalter wie `{text}`, `{schema}`, `{context}`, `{rules}`, `{validation_feedback}` und `{attempt}` enthalten.

Antwort bei Erfolg:

```json
{
  "ok": true,
  "data": {
    "name": "Max Mustermann",
    "age": 32,
    "city": "Berlin"
  },
  "error": null
}
```

## UI

`GET /`

Die Web-UI bietet vier Felder:

1. Text
2. Schema
3. Prompt
4. JSON Output

## Starten

```bash
uvicorn main:app --reload
```

Danach `http://127.0.0.1:8000/` im Browser oeffnen.

## Konfiguration

Setze `OPENAI_API_KEY`, damit die Extraktion ueber ein Modell laeuft.
