# API

## `POST /generate-json`

Erwartet:

```json
{
  "text": "...",
  "json_schema": {"type": "object"},
  "context": "optional"
}
```

Antwort bei Erfolg:

```json
{
  "data": {}
}
```

Antwort bei Fehler:

```json
{
  "error": "validation_failed"
}
```
