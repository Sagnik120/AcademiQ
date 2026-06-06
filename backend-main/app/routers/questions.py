from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database import get_db
from app.dependencies import require_educator
from app.models.user import User
from app.schemas.question import (
    QuestionCreateRequest, QuestionUpdateRequest, QuestionResponse,
    OptionResponse, ReferenceAnswerCreate, ReferenceAnswerResponse, MessageResponse
)
from app.services.question_service import (
    create_question, get_my_questions, get_question_by_id,
    get_options, get_reference_answer, update_question,
    delete_question, upsert_reference_answer
)

router = APIRouter()

def format_question(q, options=None, ref=None) -> QuestionResponse:
    return QuestionResponse(
        id=str(q.id),
        educator_id=str(q.educator_id),
        course_id=str(q.course_id) if q.course_id else None,
        question_type=q.question_type if isinstance(q.question_type, str) else q.question_type.value,
        question_text=q.question_text,
        marks=float(q.marks),
        negative_marks=float(q.negative_marks),
        explanation=q.explanation,
        difficulty_level=q.difficulty_level,
        tags=q.tags,
        is_ai_generated=q.is_ai_generated,
        options=[OptionResponse(id=str(o.id), option_text=o.option_text, is_correct=o.is_correct, order_index=o.order_index) for o in options] if options else None,
        reference_answer=ReferenceAnswerResponse(
            id=str(ref.id), question_id=str(ref.question_id),
            reference_text=ref.reference_text, grading_rubric=ref.grading_rubric,
            max_marks=float(ref.max_marks)
        ) if ref else None
    )

@router.post("/", response_model=QuestionResponse, status_code=201)
async def create(data: QuestionCreateRequest, current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    q = await create_question(data, current_user, db)
    options = await get_options(str(q.id), db)
    return format_question(q, options)

@router.get("/", response_model=List[QuestionResponse])
async def list_questions(
    question_type: Optional[str] = Query(None),
    current_user: User = Depends(require_educator),
    db: AsyncSession = Depends(get_db)
):
    questions = await get_my_questions(current_user, db, question_type)
    result = []
    for q in questions:
        options = await get_options(str(q.id), db)
        ref = await get_reference_answer(str(q.id), db)
        result.append(format_question(q, options, ref))
    return result

@router.get("/{question_id}", response_model=QuestionResponse)
async def get_one(question_id: str, current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    q = await get_question_by_id(question_id, db)
    if str(q.educator_id) != str(current_user.id):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not your question")
    options = await get_options(question_id, db)
    ref = await get_reference_answer(question_id, db)
    return format_question(q, options, ref)

@router.patch("/{question_id}", response_model=QuestionResponse)
async def update(question_id: str, data: QuestionUpdateRequest, current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    q = await update_question(question_id, data, current_user, db)
    options = await get_options(question_id, db)
    ref = await get_reference_answer(question_id, db)
    return format_question(q, options, ref)

@router.delete("/{question_id}", response_model=MessageResponse)
async def delete(question_id: str, current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    await delete_question(question_id, current_user, db)
    return MessageResponse(message="Question deleted")

@router.post("/{question_id}/reference-answer", response_model=ReferenceAnswerResponse)
async def set_reference_answer(question_id: str, data: ReferenceAnswerCreate, current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    ref = await upsert_reference_answer(question_id, data, current_user, db)
    return ReferenceAnswerResponse(
        id=str(ref.id), question_id=str(ref.question_id),
        reference_text=ref.reference_text, grading_rubric=ref.grading_rubric,
        max_marks=float(ref.max_marks)
    )
