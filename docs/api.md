# API

## `POST /generate-json`

Erwartet:

```json
{
  "text": "...",
  "schema": {"type": "object"},
  "context": {
    "now": "2026-05-17T12:00:00Z",
    "timezone": "Europe/Berlin"
  },
  "prompt": "optional"
}
```

Antwort bei Erfolg:

```json
{
  "ok": true,
  "data": {},
  "error": null
}
```

Antwort bei Fehler:

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "validation_failed",
    "message": "...",
    "details": []
  }
}
```
