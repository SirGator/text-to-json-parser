# Architecture

## Ablauf

```text
Request -> API Validation -> Schema Check -> Prompt Build -> LLM Structured Output -> JSON Validation -> Normalisierung
```

## Bausteine

- API Layer
- Schema Parser
- Prompt Builder
- LLM Executor
- Validator
- Normalizer
