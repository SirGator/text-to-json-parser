from fastapi import APIRouter, HTTPException

from src.api.request_models import GenerateJsonRequest
from src.api.response_models import GenerateJsonResponse
from src.llm.llm_client import active_backend, ping_backend
from src.llm.structured_output import supports_structured_output
from src.pipeline.flow import generate_json_flow
from src.schema.json_validator import validate_json
from src.schema.schema_registry import default_schemas, get_schema

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """Liveness + Readiness in einem Endpoint.

    Wird vom ARCS interpretation_worker regelmäßig gepingt.
    """
    backend = active_backend()
    provider_ok = False
    provider_error: str | None = None
    try:
        provider_ok = await ping_backend(backend)
    except Exception as exc:  # pragma: no cover - defensive
        provider_error = str(exc)

    return {
        "ok": True,
        "service": "text-to-json-parser",
        "version": "0.2.0",
        "backend": backend,
        "provider_reachable": provider_ok,
        "structured_output": supports_structured_output(),
        "provider_error": provider_error,
    }


@router.get("/schemas")
async def list_schemas() -> dict:
    """Liste der eingebauten Schemas, die der Parser kennt.

    Wichtig für ARCS: `arcs.interpretation_proposal.v1` ist die
    Brücke zwischen parser und ARCS Core.
    """
    return {"ok": True, "schemas": list(default_schemas().keys())}


@router.get("/schemas/{schema_id}")
async def fetch_schema(schema_id: str) -> dict:
    schema = get_schema(schema_id)
    if schema is None:
        raise HTTPException(status_code=404, detail=f"unknown schema: {schema_id}")
    return {"ok": True, "schema_id": schema_id, "schema": schema}


@router.post("/validate")
async def validate_against_schema(body: dict) -> dict:
    """Prüft, ob `data` zu `schema` passt. Nützlich für ARCS Smoke-Tests."""
    data = body.get("data")
    schema = body.get("schema")
    if not isinstance(data, dict) or not isinstance(schema, dict):
        raise HTTPException(status_code=400, detail="data and schema required")
    try:
        validate_json(data, schema)
    except Exception as exc:
        return {"ok": False, "error": {"code": "invalid_output", "message": str(exc)}}
    return {"ok": True}


@router.post("/generate-json", response_model=GenerateJsonResponse)
async def generate_json(request: GenerateJsonRequest):
    return await generate_json_flow(request)
