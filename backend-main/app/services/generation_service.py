import uuid
import logging
import httpx
from typing import Optional, List
from fastapi import HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.generation import GenerationJob, GeneratedQuestion, GenerationStatus
from app.models.question import Question, QuestionOption, ReferenceAnswer, QuestionType

logger = logging.getLogger(__name__)

def _to_uuid(val):
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError):
        return val


async def process_generation_job(
    job_id: str,
    file_b64: Optional[str],
    raw_text: Optional[str],
    difficulty_hint: Optional[str],
    session_override: Optional[AsyncSession] = None
):
    """
    Background task to extract text (if PDF supplied), invoke GenAI question generation,
    and persist proposed questions in generated_questions table.
    """
    async def _execute(db: AsyncSession):
        job_uuid = _to_uuid(job_id)
        job_res = await db.execute(select(GenerationJob).where(GenerationJob.id == job_uuid))
        job = job_res.scalar_one_or_none()
        if not job:
            logger.error("GenerationJob %s not found for processing", job_id)
            return

        job.status = GenerationStatus.processing
        await db.commit()

        content_text = (raw_text or "").strip()

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                # 1. Extract PDF text if file provided
                if file_b64:
                    pdf_url = f"{settings.GENAI_SERVICE_URL.rstrip('/')}/extract-pdf"
                    pdf_resp = await client.post(pdf_url, json={"file_bytes": file_b64})
                    if pdf_resp.status_code == 200:
                        pdf_data = pdf_resp.json()
                        extracted = pdf_data.get("text", "").strip()
                        if extracted:
                            content_text = extracted
                    else:
                        raise ValueError(f"PDF extraction failed with status {pdf_resp.status_code}: {pdf_resp.text}")

                # Boundary validation: ensure readable content exists
                if not content_text or len(content_text) < 10:
                    raise ValueError("Document contains no readable or meaningful text for question generation.")

                # 2. Invoke GenAI question generator
                gen_url = f"{settings.GENAI_SERVICE_URL.rstrip('/')}/generate-questions"
                gen_payload = {
                    "content": content_text,
                    "mcq_count": job.mcq_count,
                    "msq_count": job.msq_count,
                    "text_count": job.text_count,
                    "difficulty_hint": difficulty_hint
                }

                gen_resp = await client.post(gen_url, json=gen_payload)
                if gen_resp.status_code != 200:
                    raise ValueError(f"GenAI generation endpoint failed with status {gen_resp.status_code}: {gen_resp.text}")

                gen_data = gen_resp.json()
                questions_list = gen_data.get("questions", [])

                # 3. Save candidate questions into database
                saved_count = 0
                for q_item in questions_list:
                    gen_q = GeneratedQuestion(
                        job_id=job.id,
                        question_type=q_item.get("type", "mcq"),
                        question_text=q_item.get("question_text", ""),
                        options_json=q_item.get("options"),
                        reference_answer=q_item.get("reference_answer"),
                        explanation=q_item.get("explanation"),
                        difficulty_level=int(q_item.get("difficulty_level", 3)),
                        marks=float(q_item.get("marks", 1.0)),
                        is_approved=False
                    )
                    db.add(gen_q)
                    saved_count += 1

                job.total_generated = saved_count
                job.status = GenerationStatus.completed
                await db.commit()
                logger.info("Successfully generated %d questions for job %s", saved_count, job_id)

            except Exception as e:
                logger.error("Job %s generation failed: %s", job_id, e)
                job.status = GenerationStatus.failed
                job.error_message = str(e)
                await db.commit()

    if session_override is not None:
        await _execute(session_override)
    else:
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await _execute(session)


async def approve_generated_question(
    job_id: str,
    question_id: str,
    educator_id: str,
    db: AsyncSession
) -> dict:
    """
    Transfers a candidate generated question into the educator's main Question Bank.
    """
    job_uuid = _to_uuid(job_id)
    q_uuid = _to_uuid(question_id)
    edu_uuid = _to_uuid(educator_id)

    # 1. Fetch job and verify educator ownership
    job_res = await db.execute(select(GenerationJob).where(GenerationJob.id == job_uuid))
    job = job_res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found")
    if job.educator_id != edu_uuid:
        raise HTTPException(status_code=403, detail="Not authorized to approve questions for this job")

    # 2. Fetch candidate question
    gen_res = await db.execute(
        select(GeneratedQuestion).where(
            and_(GeneratedQuestion.id == q_uuid, GeneratedQuestion.job_id == job_uuid)
        )
    )
    gen_q = gen_res.scalar_one_or_none()
    if not gen_q:
        raise HTTPException(status_code=404, detail="Generated question not found")

    if gen_q.is_approved and gen_q.approved_question_id:
        return {
            "message": "Question already approved",
            "generated_question_id": str(gen_q.id),
            "approved_question_id": str(gen_q.approved_question_id)
        }

    # Map question type
    q_type = QuestionType.mcq
    if gen_q.question_type == "msq":
        q_type = QuestionType.msq
    elif gen_q.question_type == "text":
        q_type = QuestionType.text

    # 3. Create question in main question bank
    new_question = Question(
        educator_id=edu_uuid,
        course_id=job.course_id,
        question_type=q_type,
        question_text=gen_q.question_text,
        marks=gen_q.marks,
        explanation=gen_q.explanation,
        difficulty_level=gen_q.difficulty_level,
        is_ai_generated=True,
        ai_generation_job_id=job.id
    )
    db.add(new_question)
    await db.flush()

    # 4. If options present (MCQ/MSQ), populate question_options
    if gen_q.options_json and isinstance(gen_q.options_json, list):
        for idx, opt in enumerate(gen_q.options_json):
            if isinstance(opt, dict):
                opt_row = QuestionOption(
                    question_id=new_question.id,
                    option_text=opt.get("option_text", ""),
                    is_correct=bool(opt.get("is_correct", False)),
                    order_index=int(opt.get("order_index", idx))
                )
                db.add(opt_row)

    # 5. If reference answer present (Text question), populate reference_answers
    if gen_q.reference_answer:
        ref_row = ReferenceAnswer(
            question_id=new_question.id,
            reference_text=gen_q.reference_answer,
            max_marks=float(gen_q.marks)
        )
        db.add(ref_row)

    # 6. Mark candidate as approved
    gen_q.is_approved = True
    gen_q.approved_question_id = new_question.id
    await db.commit()
    await db.refresh(new_question)

    return {
        "message": "Question successfully approved into Question Bank",
        "generated_question_id": str(gen_q.id),
        "approved_question_id": str(new_question.id)
    }
