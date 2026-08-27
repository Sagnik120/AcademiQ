from fastapi import APIRouter, HTTPException
from app.schemas import GenerateRequest, GenerateResponse
from app.services.generator import generate_questions
import logging

router = APIRouter(tags=["generation"])
logger = logging.getLogger(__name__)


@router.post("/generate-questions", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    if not request.content.strip():
        raise HTTPException(status_code=422, detail="content cannot be empty")
    try:
        return await generate_questions(request)
    except Exception as e:
        logger.error("Generation failed: %s", e)
        raise HTTPException(status_code=500, detail="Question generation failed. Try again shortly.")
