from fastapi import APIRouter
from src.api.request_models import GenerateJsonRequest
from src.api.response_models import GenerateJsonResponse
from src.pipeline.flow import generate_json_flow

router = APIRouter()

@router.post("/generate-json", response_model=GenerateJsonResponse)
async def generate_json(request: GenerateJsonRequest):
    return await generate_json_flow(request)
