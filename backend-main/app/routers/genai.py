import logging
from typing import List
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_educator
from app.models.user import User
from app.models.generation import GenerationJob, GeneratedQuestion, GenerationStatus
from app.schemas.generation import (
    GenerateQuestionsRequest,
    GenerationJobResponse,
    GeneratedQuestionResponse,
    ApproveQuestionResponse
)
from app.services.generation_service import (
    process_generation_job,
    approve_generated_question,
    _to_uuid
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/generate-questions", response_model=GenerationJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_questions(
    payload: GenerateQuestionsRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_educator),
    db: AsyncSession = Depends(get_db)
):
    """
    Submits a syllabus document (raw text or base64 PDF) for AI question generation.
    Returns immediately with a pending GenerationJob, processing questions asynchronously.
    """
    if not payload.content and not payload.file_bytes_base64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'content' (raw text) or 'file_bytes_base64' (PDF) must be provided."
        )

    course_uuid = _to_uuid(payload.course_id) if payload.course_id else None

    # 1. Create the generation job record
    job = GenerationJob(
        educator_id=current_user.id,
        course_id=course_uuid,
        status=GenerationStatus.pending,
        source_file_name=payload.source_file_name,
        mcq_count=payload.mcq_count,
        msq_count=payload.msq_count,
        text_count=payload.text_count
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # 2. Queue asynchronous background processing
    background_tasks.add_task(
        process_generation_job,
        job_id=str(job.id),
        file_b64=payload.file_bytes_base64,
        raw_text=payload.content,
        difficulty_hint=payload.difficulty_hint
    )

    return GenerationJobResponse(
        job_id=str(job.id),
        status=job.status.value if hasattr(job.status, "value") else str(job.status),
        source_file_name=job.source_file_name,
        mcq_count=job.mcq_count,
        msq_count=job.msq_count,
        text_count=job.text_count,
        total_generated=job.total_generated,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at
    )


@router.get("/generation-jobs/{job_id}", response_model=GenerationJobResponse)
async def get_generation_job(
    job_id: str,
    current_user: User = Depends(require_educator),
    db: AsyncSession = Depends(get_db)
):
    """Fetches the current progress/status of an AI question generation job."""
    job_uuid = _to_uuid(job_id)
    result = await db.execute(select(GenerationJob).where(GenerationJob.id == job_uuid))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found")

    if job.educator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this job")

    return GenerationJobResponse(
        job_id=str(job.id),
        status=job.status.value if hasattr(job.status, "value") else str(job.status),
        source_file_name=job.source_file_name,
        mcq_count=job.mcq_count,
        msq_count=job.msq_count,
        text_count=job.text_count,
        total_generated=job.total_generated,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at
    )


@router.get("/generation-jobs/{job_id}/questions", response_model=List[GeneratedQuestionResponse])
async def list_generated_questions(
    job_id: str,
    current_user: User = Depends(require_educator),
    db: AsyncSession = Depends(get_db)
):
    """Lists all candidate questions produced by an AI generation job."""
    job_uuid = _to_uuid(job_id)
    job_res = await db.execute(select(GenerationJob).where(GenerationJob.id == job_uuid))
    job = job_res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found")

    if job.educator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view questions for this job")

    q_res = await db.execute(select(GeneratedQuestion).where(GeneratedQuestion.job_id == job_uuid))
    questions = q_res.scalars().all()

    return [
        GeneratedQuestionResponse(
            id=str(q.id),
            job_id=str(q.job_id),
            question_type=q.question_type,
            question_text=q.question_text,
            options=q.options_json if isinstance(q.options_json, list) else None,
            reference_answer=q.reference_answer,
            explanation=q.explanation,
            difficulty_level=q.difficulty_level,
            marks=float(q.marks),
            is_approved=q.is_approved,
            approved_question_id=str(q.approved_question_id) if q.approved_question_id else None,
            created_at=q.created_at
        )
        for q in questions
    ]


@router.post("/generation-jobs/{job_id}/questions/{question_id}/approve", response_model=ApproveQuestionResponse)
async def approve_question(
    job_id: str,
    question_id: str,
    current_user: User = Depends(require_educator),
    db: AsyncSession = Depends(get_db)
):
    """Approves a candidate AI-generated question into the educator's primary Question Bank."""
    result = await approve_generated_question(
        job_id=job_id,
        question_id=question_id,
        educator_id=str(current_user.id),
        db=db
    )
    return ApproveQuestionResponse(**result)
