import uuid
import logging
import httpx
from typing import Optional
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.exam import Exam, ExamQuestion, ExamAttempt, AttemptResponse, GradeStatus
from app.models.question import Question, ReferenceAnswer

logger = logging.getLogger(__name__)

def _to_uuid(val):
    """Converts a string or UUID to a uuid.UUID object for SQLite/Postgres compatibility."""
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError):
        return val

async def _grade_single_response(
    resp: AttemptResponse,
    client: httpx.AsyncClient,
    db: AsyncSession
) -> float:
    """
    Grades a single text response using genai-service.
    Returns marks awarded.
    """
    student_text = (resp.text_response or "").strip()

    # Boundary Case 1: Empty or whitespace-only response
    if not student_text:
        resp.marks_obtained = 0.0
        resp.llm_score = 0.0
        resp.llm_feedback = "No answer provided."
        resp.llm_citation_highlights = {"earned_marks": [], "lost_marks": []}
        resp.grade_status = GradeStatus.graded
        resp.llm_graded_at = func.now()
        resp.llm_model_used = "system-auto-zero"
        return 0.0

    # Fetch question and reference answer
    q_uuid = _to_uuid(resp.question_id)
    q_result = await db.execute(select(Question).where(Question.id == q_uuid))
    q = q_result.scalar_one_or_none()
    if not q:
        logger.warning("Question %s not found for response %s", resp.question_id, resp.id)
        return 0.0

    ref_result = await db.execute(select(ReferenceAnswer).where(ReferenceAnswer.question_id == q_uuid))
    ref = ref_result.scalar_one_or_none()

    # Determine question max marks
    att_uuid = _to_uuid(resp.attempt_id)
    attempt_result = await db.execute(select(ExamAttempt).where(ExamAttempt.id == att_uuid))
    attempt = attempt_result.scalar_one_or_none()
    
    max_marks = float(q.marks)
    if attempt:
        eq_result = await db.execute(
            select(ExamQuestion).where(
                and_(ExamQuestion.exam_id == attempt.exam_id, ExamQuestion.question_id == q.id)
            )
        )
        eq = eq_result.scalar_one_or_none()
        if eq and eq.marks_override:
            max_marks = float(eq.marks_override)

    payload = {
        "question": q.question_text,
        "student_answer": student_text,
        "reference_answer": ref.reference_text if ref else "Comprehensive factual response expected.",
        "max_marks": max_marks,
        "grading_rubric": ref.grading_rubric if ref else None
    }

    url = f"{settings.GENAI_SERVICE_URL.rstrip('/')}/grade"
    
    try:
        response = await client.post(url, json=payload, timeout=30.0)
        if response.status_code == 200:
            data = response.json()
            awarded = float(data.get("marks_awarded", 0.0))
            # Clamp between 0 and max_marks
            awarded = max(0.0, min(awarded, max_marks))

            resp.marks_obtained = awarded
            resp.llm_score = awarded
            resp.llm_feedback = data.get("overall_feedback", "Graded successfully.")
            resp.llm_citation_highlights = data.get("citation_highlights", {})
            resp.llm_model_used = data.get("model", "gemini-2.5-flash")
            resp.llm_graded_at = func.now()
            resp.grade_status = GradeStatus.graded
            return awarded
        else:
            logger.error("GenAI service returned status %d: %s", response.status_code, response.text)
            # Retain pending state for future retry without crashing
            return 0.0
    except Exception as e:
        logger.error("Failed to connect to GenAI service at %s: %s", url, e)
        # Retain pending state
        return 0.0


async def grade_attempt_text_responses(attempt_id: str, session_override: Optional[AsyncSession] = None):
    """
    Background worker function that finds all pending text responses for an attempt,
    sends them to the GenAI grading service, updates responses, and recalculates total scores.
    """
    async def _execute(db: AsyncSession):
        att_uuid = _to_uuid(attempt_id)
        # 1. Fetch attempt and exam
        attempt_res = await db.execute(select(ExamAttempt).where(ExamAttempt.id == att_uuid))
        attempt = attempt_res.scalar_one_or_none()
        if not attempt:
            logger.error("Attempt %s not found for background grading", attempt_id)
            return

        exam_res = await db.execute(select(Exam).where(Exam.id == attempt.exam_id))
        exam = exam_res.scalar_one_or_none()

        # 2. Fetch pending text responses
        resp_res = await db.execute(
            select(AttemptResponse).where(
                and_(
                    AttemptResponse.attempt_id == att_uuid,
                    AttemptResponse.grade_status == GradeStatus.pending,
                    AttemptResponse.is_skipped == False
                )
            )
        )
        pending_responses = resp_res.scalars().all()

        if not pending_responses:
            logger.info("No pending text responses for attempt %s", attempt_id)
            return

        # 3. Grade each pending response using an async HTTP client
        async with httpx.AsyncClient() as client:
            for resp in pending_responses:
                await _grade_single_response(resp, client, db)

        # 4. Recalculate total score for the attempt
        all_res = await db.execute(select(AttemptResponse).where(AttemptResponse.attempt_id == att_uuid))
        all_responses = all_res.scalars().all()

        total_marks = 0.0
        for r in all_responses:
            if r.marks_obtained is not None:
                total_marks += float(r.marks_obtained)

        attempt.total_marks_obtained = max(0.0, total_marks)

        if exam and exam.total_marks and float(exam.total_marks) > 0:
            attempt.percentage = round((max(0.0, total_marks) / float(exam.total_marks)) * 100, 2)

        if exam and exam.passing_marks:
            attempt.is_passed = total_marks >= float(exam.passing_marks)

        await db.commit()
        logger.info("Successfully finished GenAI grading for attempt %s: Total marks %.2f", attempt_id, attempt.total_marks_obtained)

    if session_override is not None:
        await _execute(session_override)
    else:
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await _execute(session)
