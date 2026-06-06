from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from fastapi import HTTPException
from app.models.exam import Exam, ExamQuestion, ExamAttempt, AttemptResponse, ExamType, ExamStatus, AttemptStatus, GradeStatus
from app.models.question import Question, QuestionOption, ReferenceAnswer
from app.models.user import User
from app.schemas.exam import ExamCreateRequest, ExamUpdateRequest, AddQuestionRequest, SubmitResponseRequest
import uuid
import random
from datetime import datetime, timezone

# ── Educator: Exam CRUD ───────────────────────────

async def create_exam(data: ExamCreateRequest, educator: User, db: AsyncSession):
    exam = Exam(
        course_id=uuid.UUID(data.course_id),
        educator_id=educator.id,
        title=data.title,
        description=data.description,
        exam_type=data.exam_type.value,
        instructions=data.instructions,
        duration_minutes=data.duration_minutes,
        passing_marks=data.passing_marks,
        max_attempts=data.max_attempts,
        shuffle_questions=data.shuffle_questions,
        shuffle_options=data.shuffle_options,
        show_result_immediately=data.show_result_immediately,
        is_proctored=data.is_proctored,
        scheduled_start=data.scheduled_start,
        scheduled_end=data.scheduled_end
    )
    db.add(exam)
    await db.commit()
    await db.refresh(exam)
    return exam

async def get_exam_by_id(exam_id: str, db: AsyncSession):
    result = await db.execute(
        select(Exam).where(and_(Exam.id == exam_id, Exam.is_deleted == False))
    )
    exam = result.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam

async def get_educator_exams(educator: User, db: AsyncSession):
    result = await db.execute(
        select(Exam).where(
            and_(Exam.educator_id == educator.id, Exam.is_deleted == False)
        ).order_by(Exam.created_at.desc())
    )
    return result.scalars().all()

async def update_exam(exam_id: str, data: ExamUpdateRequest, educator: User, db: AsyncSession):
    exam = await get_exam_by_id(exam_id, db)
    if str(exam.educator_id) != str(educator.id):
        raise HTTPException(status_code=403, detail="Not your exam")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(exam, field, value)
    await db.commit()
    await db.refresh(exam)
    return exam

async def publish_exam(exam_id: str, educator: User, db: AsyncSession):
    exam = await get_exam_by_id(exam_id, db)
    if str(exam.educator_id) != str(educator.id):
        raise HTTPException(status_code=403, detail="Not your exam")
    # Calculate total marks from exam questions
    result = await db.execute(
        select(ExamQuestion).where(ExamQuestion.exam_id == exam_id)
    )
    eq_list = result.scalars().all()
    if not eq_list:
        raise HTTPException(status_code=400, detail="Cannot publish exam with no questions")
    total = 0
    for eq in eq_list:
        if eq.marks_override:
            total += float(eq.marks_override)
        else:
            q_result = await db.execute(select(Question).where(Question.id == eq.question_id))
            q = q_result.scalar_one_or_none()
            if q:
                total += float(q.marks)
    exam.total_marks = total
    exam.status = ExamStatus.active
    await db.commit()
    await db.refresh(exam)
    return exam

async def delete_exam(exam_id: str, educator: User, db: AsyncSession):
    exam = await get_exam_by_id(exam_id, db)
    if str(exam.educator_id) != str(educator.id):
        raise HTTPException(status_code=403, detail="Not your exam")
    exam.is_deleted = True
    await db.commit()

# ── Exam Questions ────────────────────────────────

async def add_question_to_exam(exam_id: str, data: AddQuestionRequest, educator: User, db: AsyncSession):
    exam = await get_exam_by_id(exam_id, db)
    if str(exam.educator_id) != str(educator.id):
        raise HTTPException(status_code=403, detail="Not your exam")
    existing = await db.execute(
        select(ExamQuestion).where(
            and_(ExamQuestion.exam_id == exam_id, ExamQuestion.question_id == data.question_id)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Question already in exam")
    eq = ExamQuestion(
        exam_id=uuid.UUID(exam_id),
        question_id=uuid.UUID(data.question_id),
        order_index=data.order_index,
        marks_override=data.marks_override
    )
    db.add(eq)
    await db.commit()
    await db.refresh(eq)
    return eq

async def remove_question_from_exam(exam_id: str, question_id: str, educator: User, db: AsyncSession):
    exam = await get_exam_by_id(exam_id, db)
    if str(exam.educator_id) != str(educator.id):
        raise HTTPException(status_code=403, detail="Not your exam")
    result = await db.execute(
        select(ExamQuestion).where(
            and_(ExamQuestion.exam_id == exam_id, ExamQuestion.question_id == question_id)
        )
    )
    eq = result.scalar_one_or_none()
    if not eq:
        raise HTTPException(status_code=404, detail="Question not in exam")
    await db.delete(eq)
    await db.commit()

async def get_exam_questions(exam_id: str, db: AsyncSession):
    result = await db.execute(
        select(ExamQuestion).where(ExamQuestion.exam_id == exam_id).order_by(ExamQuestion.order_index)
    )
    return result.scalars().all()

# ── Learner: Attempt Flow ─────────────────────────

async def start_attempt(exam_id: str, learner: User, db: AsyncSession):
    exam = await get_exam_by_id(exam_id, db)
    if exam.status != ExamStatus.active:
        raise HTTPException(status_code=400, detail="Exam is not active")

    # Check max attempts
    result = await db.execute(
        select(ExamAttempt).where(
            and_(ExamAttempt.exam_id == exam_id, ExamAttempt.learner_id == learner.id)
        )
    )
    existing_attempts = result.scalars().all()
    completed = [a for a in existing_attempts if a.status == AttemptStatus.submitted]
    if len(completed) >= exam.max_attempts:
        raise HTTPException(status_code=400, detail="Maximum attempts reached")

    in_progress = [a for a in existing_attempts if a.status == AttemptStatus.in_progress]
    if in_progress:
        raise HTTPException(status_code=400, detail="You have an attempt already in progress")

    attempt_number = len(existing_attempts) + 1
    attempt = ExamAttempt(
        exam_id=uuid.UUID(exam_id),
        learner_id=learner.id,
        attempt_number=attempt_number
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)

    # Get questions
    eq_result = await db.execute(
        select(ExamQuestion).where(ExamQuestion.exam_id == exam_id).order_by(ExamQuestion.order_index)
    )
    eq_list = eq_result.scalars().all()
    if exam.shuffle_questions:
        random.shuffle(eq_list)

    questions_for_attempt = []
    for eq in eq_list:
        q_result = await db.execute(select(Question).where(Question.id == eq.question_id))
        q = q_result.scalar_one_or_none()
        if not q:
            continue
        q_data = {
            "id": str(q.id),
            "question_type": q.question_type if isinstance(q.question_type, str) else q.question_type.value,
            "question_text": q.question_text,
            "marks": float(eq.marks_override) if eq.marks_override else float(q.marks),
            "negative_marks": float(q.negative_marks),
            "order_index": eq.order_index,
            "options": None
        }
        if q.question_type in ["mcq", "msq"]:
            opt_result = await db.execute(
                select(QuestionOption).where(QuestionOption.question_id == q.id).order_by(QuestionOption.order_index)
            )
            opts = opt_result.scalars().all()
            if exam.shuffle_options:
                opts = list(opts)
                random.shuffle(opts)
            # Never expose is_correct to learner
            q_data["options"] = [
                {"id": str(o.id), "option_text": o.option_text, "order_index": o.order_index}
                for o in opts
            ]
        questions_for_attempt.append(q_data)

    return attempt, exam, questions_for_attempt

async def save_response(attempt_id: str, data: SubmitResponseRequest, learner: User, db: AsyncSession):
    result = await db.execute(
        select(ExamAttempt).where(
            and_(ExamAttempt.id == attempt_id, ExamAttempt.learner_id == learner.id)
        )
    )
    attempt = result.scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.status != AttemptStatus.in_progress:
        raise HTTPException(status_code=400, detail="Attempt is not in progress")

    existing = await db.execute(
        select(AttemptResponse).where(
            and_(AttemptResponse.attempt_id == attempt_id, AttemptResponse.question_id == data.question_id)
        )
    )
    resp = existing.scalar_one_or_none()

    selected_ids = [uuid.UUID(oid) for oid in data.selected_option_ids] if data.selected_option_ids else None

    if resp:
        resp.selected_option_ids = selected_ids
        resp.text_response = data.text_response
        resp.time_spent_seconds = data.time_spent_seconds
        resp.is_skipped = data.is_skipped
    else:
        resp = AttemptResponse(
            attempt_id=uuid.UUID(attempt_id),
            question_id=uuid.UUID(data.question_id),
            selected_option_ids=selected_ids,
            text_response=data.text_response,
            time_spent_seconds=data.time_spent_seconds,
            is_skipped=data.is_skipped
        )
        db.add(resp)
    await db.commit()
    return resp

async def submit_attempt(attempt_id: str, learner: User, db: AsyncSession):
    result = await db.execute(
        select(ExamAttempt).where(
            and_(ExamAttempt.id == attempt_id, ExamAttempt.learner_id == learner.id)
        )
    )
    attempt = result.scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.status != AttemptStatus.in_progress:
        raise HTTPException(status_code=400, detail="Attempt already submitted")

    exam = await get_exam_by_id(str(attempt.exam_id), db)

    # Get all responses
    resp_result = await db.execute(
        select(AttemptResponse).where(AttemptResponse.attempt_id == attempt_id)
    )
    responses = resp_result.scalars().all()

    total_marks = 0.0

    for resp in responses:
        if resp.is_skipped:
            resp.marks_obtained = 0
            resp.grade_status = GradeStatus.graded
            continue

        q_result = await db.execute(select(Question).where(Question.id == resp.question_id))
        q = q_result.scalar_one_or_none()
        if not q:
            continue

        # Get marks for this question in this exam
        eq_result = await db.execute(
            select(ExamQuestion).where(
                and_(ExamQuestion.exam_id == str(attempt.exam_id), ExamQuestion.question_id == str(resp.question_id))
            )
        )
        eq = eq_result.scalar_one_or_none()
        question_marks = float(eq.marks_override) if eq and eq.marks_override else float(q.marks)
        negative = float(q.negative_marks)

        q_type = q.question_type if isinstance(q.question_type, str) else q.question_type.value

        if q_type == "text":
            # LLM grading — mark as pending, background task handles it
            resp.grade_status = GradeStatus.pending
            continue

        elif q_type == "mcq":
            if resp.selected_option_ids:
                opt_result = await db.execute(
                    select(QuestionOption).where(
                        and_(QuestionOption.question_id == q.id, QuestionOption.is_correct == True)
                    )
                )
                correct_opt = opt_result.scalar_one_or_none()
                if correct_opt and str(correct_opt.id) in [str(oid) for oid in resp.selected_option_ids]:
                    resp.marks_obtained = question_marks
                    total_marks += question_marks
                else:
                    resp.marks_obtained = -negative
                    total_marks -= negative
            else:
                resp.marks_obtained = 0
            resp.grade_status = GradeStatus.graded

        elif q_type == "msq":
            if resp.selected_option_ids:
                opt_result = await db.execute(
                    select(QuestionOption).where(QuestionOption.question_id == q.id)
                )
                all_opts = opt_result.scalars().all()
                correct_ids = {str(o.id) for o in all_opts if o.is_correct}
                selected_ids_str = {str(oid) for oid in resp.selected_option_ids}
                if selected_ids_str == correct_ids:
                    resp.marks_obtained = question_marks
                    total_marks += question_marks
                else:
                    resp.marks_obtained = -negative
                    total_marks -= negative
            else:
                resp.marks_obtained = 0
            resp.grade_status = GradeStatus.graded

    now = datetime.now(timezone.utc)
    time_taken = int((now - attempt.started_at.replace(tzinfo=timezone.utc)).total_seconds())

    attempt.status = AttemptStatus.submitted
    attempt.submitted_at = now
    attempt.time_taken_seconds = time_taken
    attempt.total_marks_obtained = max(0, total_marks)  # floor at 0
    if exam.total_marks and float(exam.total_marks) > 0:
        attempt.percentage = round((max(0, total_marks) / float(exam.total_marks)) * 100, 2)
    if exam.passing_marks:
        attempt.is_passed = total_marks >= float(exam.passing_marks)

    await db.commit()
    await db.refresh(attempt)
    return attempt

async def get_attempt_result(attempt_id: str, learner: User, db: AsyncSession):
    result = await db.execute(
        select(ExamAttempt).where(
            and_(ExamAttempt.id == attempt_id, ExamAttempt.learner_id == learner.id)
        )
    )
    attempt = result.scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    resp_result = await db.execute(
        select(AttemptResponse).where(AttemptResponse.attempt_id == attempt_id)
    )
    responses = resp_result.scalars().all()

    response_data = []
    for r in responses:
        q_result = await db.execute(select(Question).where(Question.id == r.question_id))
        q = q_result.scalar_one_or_none()
        response_data.append({
            "question_id": str(r.question_id),
            "question_text": q.question_text if q else "",
            "question_type": q.question_type if isinstance(q.question_type, str) else q.question_type.value if q else "",
            "marks_obtained": float(r.marks_obtained) if r.marks_obtained is not None else None,
            "grade_status": r.grade_status if isinstance(r.grade_status, str) else r.grade_status.value,
            "text_response": r.text_response,
            "llm_feedback": r.llm_feedback,
            "llm_citation_highlights": r.llm_citation_highlights,
            "is_skipped": r.is_skipped
        })

    return attempt, response_data
