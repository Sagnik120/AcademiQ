from fastapi import APIRouter, HTTPException
from app.schemas import GradeRequest, GradeResponse
from app.services.grader import grade_answer
import logging

router = APIRouter(tags=["grading"])
logger = logging.getLogger(__name__)


@router.post("/grade", response_model=GradeResponse)
async def grade(request: GradeRequest):
    try:
        return await grade_answer(request)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Grading failed: %s", e)
        raise HTTPException(status_code=500, detail="Grading failed after retries. Try again shortly.")
