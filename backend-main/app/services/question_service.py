from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from fastapi import HTTPException
from app.models.question import Question, QuestionOption, ReferenceAnswer, QuestionType
from app.models.user import User
from app.schemas.question import QuestionCreateRequest, QuestionUpdateRequest, ReferenceAnswerCreate
import uuid

async def create_question(data: QuestionCreateRequest, educator: User, db: AsyncSession):
    # Validate options for mcq/msq
    if data.question_type in [QuestionType.mcq, QuestionType.msq]:
        if not data.options or len(data.options) < 2:
            raise HTTPException(status_code=400, detail="MCQ/MSQ questions need at least 2 options")
        correct_count = sum(1 for o in data.options if o.is_correct)
        if data.question_type == QuestionType.mcq and correct_count != 1:
            raise HTTPException(status_code=400, detail="MCQ must have exactly 1 correct option")
        if data.question_type == QuestionType.msq and correct_count < 2:
            raise HTTPException(status_code=400, detail="MSQ must have at least 2 correct options")

    question = Question(
        educator_id=educator.id,
        course_id=uuid.UUID(data.course_id) if data.course_id else None,
        question_type=data.question_type.value,
        question_text=data.question_text,
        marks=data.marks,
        negative_marks=data.negative_marks,
        explanation=data.explanation,
        difficulty_level=data.difficulty_level,
        tags=data.tags
    )
    db.add(question)
    await db.flush()  # get question.id before adding options

    if data.options:
        for opt in data.options:
            option = QuestionOption(
                question_id=question.id,
                option_text=opt.option_text,
                is_correct=opt.is_correct,
                order_index=opt.order_index
            )
            db.add(option)

    await db.commit()
    await db.refresh(question)
    return question

async def get_my_questions(educator: User, db: AsyncSession, question_type: str = None):
    query = select(Question).where(
        and_(Question.educator_id == educator.id, Question.is_deleted == False)
    )
    if question_type:
        query = query.where(Question.question_type == question_type)
    result = await db.execute(query.order_by(Question.created_at.desc()))
    return result.scalars().all()

async def get_question_by_id(question_id: str, db: AsyncSession):
    result = await db.execute(
        select(Question).where(and_(Question.id == question_id, Question.is_deleted == False))
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    return q

async def get_options(question_id: str, db: AsyncSession):
    result = await db.execute(
        select(QuestionOption).where(QuestionOption.question_id == question_id).order_by(QuestionOption.order_index)
    )
    return result.scalars().all()

async def get_reference_answer(question_id: str, db: AsyncSession):
    result = await db.execute(
        select(ReferenceAnswer).where(ReferenceAnswer.question_id == question_id)
    )
    return result.scalar_one_or_none()

async def update_question(question_id: str, data: QuestionUpdateRequest, educator: User, db: AsyncSession):
    q = await get_question_by_id(question_id, db)
    if str(q.educator_id) != str(educator.id):
        raise HTTPException(status_code=403, detail="Not your question")
    if data.question_text is not None:
        q.question_text = data.question_text
    if data.marks is not None:
        q.marks = data.marks
    if data.negative_marks is not None:
        q.negative_marks = data.negative_marks
    if data.explanation is not None:
        q.explanation = data.explanation
    if data.difficulty_level is not None:
        q.difficulty_level = data.difficulty_level
    if data.tags is not None:
        q.tags = data.tags
    await db.commit()
    await db.refresh(q)
    return q

async def delete_question(question_id: str, educator: User, db: AsyncSession):
    q = await get_question_by_id(question_id, db)
    if str(q.educator_id) != str(educator.id):
        raise HTTPException(status_code=403, detail="Not your question")
    q.is_deleted = True
    await db.commit()

async def upsert_reference_answer(question_id: str, data: ReferenceAnswerCreate, educator: User, db: AsyncSession):
    q = await get_question_by_id(question_id, db)
    if str(q.educator_id) != str(educator.id):
        raise HTTPException(status_code=403, detail="Not your question")
    if q.question_type != "text":
        raise HTTPException(status_code=400, detail="Reference answers are only for text questions")

    existing = await get_reference_answer(question_id, db)
    if existing:
        existing.reference_text = data.reference_text
        existing.grading_rubric = data.grading_rubric
        existing.max_marks = data.max_marks
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        ref = ReferenceAnswer(
            question_id=uuid.UUID(question_id),
            reference_text=data.reference_text,
            grading_rubric=data.grading_rubric,
            max_marks=data.max_marks
        )
        db.add(ref)
        await db.commit()
        await db.refresh(ref)
        return ref
