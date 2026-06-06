from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.database import get_db
from app.dependencies import require_educator, require_learner
from app.models.user import User
from app.schemas.exam import (
    ExamCreateRequest, ExamUpdateRequest, ExamResponse,
    AddQuestionRequest, ExamQuestionResponse,
    AttemptStartResponse, SubmitResponseRequest,
    AttemptResultResponse, MessageResponse, QuestionForAttempt
)
from app.services.exam_service import (
    create_exam, get_exam_by_id, get_educator_exams, update_exam,
    publish_exam, delete_exam, add_question_to_exam,
    remove_question_from_exam, get_exam_questions,
    start_attempt, save_response, submit_attempt, get_attempt_result
)

router = APIRouter()

def fmt_exam(e) -> ExamResponse:
    return ExamResponse(
        id=str(e.id), course_id=str(e.course_id), educator_id=str(e.educator_id),
        title=e.title, description=e.description,
        exam_type=e.exam_type if isinstance(e.exam_type, str) else e.exam_type.value,
        status=e.status if isinstance(e.status, str) else e.status.value,
        duration_minutes=e.duration_minutes,
        total_marks=float(e.total_marks) if e.total_marks else None,
        passing_marks=float(e.passing_marks) if e.passing_marks else None,
        max_attempts=e.max_attempts, shuffle_questions=e.shuffle_questions,
        shuffle_options=e.shuffle_options, show_result_immediately=e.show_result_immediately,
        is_proctored=e.is_proctored, scheduled_start=e.scheduled_start, scheduled_end=e.scheduled_end
    )

# ── Educator ──────────────────────────────────────
@router.post("/educator/exams", response_model=ExamResponse, status_code=201)
async def create(data: ExamCreateRequest, current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    e = await create_exam(data, current_user, db)
    return fmt_exam(e)

@router.get("/educator/exams", response_model=List[ExamResponse])
async def list_exams(current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    exams = await get_educator_exams(current_user, db)
    return [fmt_exam(e) for e in exams]

@router.get("/educator/exams/{exam_id}", response_model=ExamResponse)
async def get_one(exam_id: str, current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    e = await get_exam_by_id(exam_id, db)
    return fmt_exam(e)

@router.patch("/educator/exams/{exam_id}", response_model=ExamResponse)
async def update(exam_id: str, data: ExamUpdateRequest, current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    e = await update_exam(exam_id, data, current_user, db)
    return fmt_exam(e)

@router.post("/educator/exams/{exam_id}/publish", response_model=ExamResponse)
async def publish(exam_id: str, current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    e = await publish_exam(exam_id, current_user, db)
    return fmt_exam(e)

@router.delete("/educator/exams/{exam_id}", response_model=MessageResponse)
async def delete(exam_id: str, current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    await delete_exam(exam_id, current_user, db)
    return MessageResponse(message="Exam deleted")

@router.post("/educator/exams/{exam_id}/questions", response_model=ExamQuestionResponse, status_code=201)
async def add_question(exam_id: str, data: AddQuestionRequest, current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    eq = await add_question_to_exam(exam_id, data, current_user, db)
    return ExamQuestionResponse(
        id=str(eq.id), exam_id=str(eq.exam_id), question_id=str(eq.question_id),
        order_index=eq.order_index,
        marks_override=float(eq.marks_override) if eq.marks_override else None
    )

@router.delete("/educator/exams/{exam_id}/questions/{question_id}", response_model=MessageResponse)
async def remove_question(exam_id: str, question_id: str, current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    await remove_question_from_exam(exam_id, question_id, current_user, db)
    return MessageResponse(message="Question removed from exam")

@router.get("/educator/exams/{exam_id}/questions", response_model=List[ExamQuestionResponse])
async def list_questions(exam_id: str, current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    eqs = await get_exam_questions(exam_id, db)
    return [ExamQuestionResponse(
        id=str(eq.id), exam_id=str(eq.exam_id), question_id=str(eq.question_id),
        order_index=eq.order_index,
        marks_override=float(eq.marks_override) if eq.marks_override else None
    ) for eq in eqs]

# ── Learner ───────────────────────────────────────
@router.post("/learner/exams/{exam_id}/attempts", response_model=AttemptStartResponse, status_code=201)
async def start(exam_id: str, current_user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)):
    attempt, exam, questions = await start_attempt(exam_id, current_user, db)
    return AttemptStartResponse(
        attempt_id=str(attempt.id),
        exam_id=str(exam.id),
        duration_minutes=exam.duration_minutes,
        started_at=attempt.started_at,
        questions=[QuestionForAttempt(**q) for q in questions]
    )

@router.post("/learner/attempts/{attempt_id}/respond", response_model=MessageResponse)
async def respond(attempt_id: str, data: SubmitResponseRequest, current_user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)):
    await save_response(attempt_id, data, current_user, db)
    return MessageResponse(message="Response saved")

@router.post("/learner/attempts/{attempt_id}/submit", response_model=AttemptResultResponse)
async def submit(attempt_id: str, current_user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)):
    attempt = await submit_attempt(attempt_id, current_user, db)
    return AttemptResultResponse(
        attempt_id=str(attempt.id), exam_id=str(attempt.exam_id),
        status=attempt.status if isinstance(attempt.status, str) else attempt.status.value,
        total_marks_obtained=float(attempt.total_marks_obtained) if attempt.total_marks_obtained is not None else None,
        percentage=float(attempt.percentage) if attempt.percentage else None,
        is_passed=attempt.is_passed,
        time_taken_seconds=attempt.time_taken_seconds
    )

@router.get("/learner/attempts/{attempt_id}/result", response_model=AttemptResultResponse)
async def get_result(attempt_id: str, current_user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)):
    attempt, responses = await get_attempt_result(attempt_id, current_user, db)
    return AttemptResultResponse(
        attempt_id=str(attempt.id), exam_id=str(attempt.exam_id),
        status=attempt.status if isinstance(attempt.status, str) else attempt.status.value,
        total_marks_obtained=float(attempt.total_marks_obtained) if attempt.total_marks_obtained is not None else None,
        percentage=float(attempt.percentage) if attempt.percentage else None,
        is_passed=attempt.is_passed,
        time_taken_seconds=attempt.time_taken_seconds,
        responses=responses
    )
