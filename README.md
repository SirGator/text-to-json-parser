# Text to JSON API

Kleine API, die Freitext zusammen mit einem JSON Schema entgegennimmt und daraus schema-konformes JSON erzeugt.

## Endpunkt

`POST /generate-json`

Optional kannst du im Request ein eigenes `prompt`-Feld senden. Es wird als Template behandelt und kann Platzhalter wie `{text}`, `{schema}`, `{context}`, `{rules}`, `{validation_feedback}` und `{attempt}` enthalten.

## UI

`GET /`

Im Browser gibt es eine kleine Oberfläche mit 3 Feldern:

1. Text-Eingabe
2. Schema-Eingabe
3. JSON-Ausgabe

Beispiel:

```json
{
  "text": "Max Mustermann ist 32 Jahre alt und wohnt in Berlin.",
  "prompt": "Extrahiere aus {text} nur die Felder name, age und city. Schema: {schema}. Gib nur JSON zurück.",
  "schema": {
    "type": "object",
    "properties": {
      "name": { "type": "string" },
      "age": { "type": "integer" },
      "city": { "type": "string" }
    },
    "required": ["name", "age", "city"],
    "additionalProperties": false
  }
}
```

Antwort:

```json
{
  "data": {
    "name": "Max Mustermann",
    "age": 32,
    "city": "Berlin"
  }
}
```

## Starten

```bash
uvicorn main:app --reload
```

Dann im Browser `http://127.0.0.1:8000/` öffnen.

Oder:

```bash
text-to-json-api
```

## Konfiguration

Setze `OPENAI_API_KEY`, damit die Extraktion über ein Modell läuft.
# text-to-json-parser
