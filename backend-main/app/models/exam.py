import uuid
from sqlalchemy import Column, String, Boolean, Enum as PgEnum, TIMESTAMP, Text, Integer, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.sql import func
from app.database import Base
import enum

class ExamType(str, enum.Enum):
    quiz = "quiz"
    test = "test"

class ExamStatus(str, enum.Enum):
    draft = "draft"
    scheduled = "scheduled"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"

class AttemptStatus(str, enum.Enum):
    in_progress = "in_progress"
    submitted = "submitted"
    cancelled = "cancelled"
    timed_out = "timed_out"

class GradeStatus(str, enum.Enum):
    pending = "pending"
    graded = "graded"
    reviewed = "reviewed"

class Exam(Base):
    __tablename__ = "exams"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    educator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    exam_type = Column(PgEnum(ExamType, name="exam_type", create_type=False), nullable=False)
    status = Column(PgEnum(ExamStatus, name="exam_status", create_type=False), default=ExamStatus.draft)
    instructions = Column(Text, nullable=True)
    duration_minutes = Column(Integer, nullable=False)
    total_marks = Column(Numeric(7, 2), nullable=True)
    passing_marks = Column(Numeric(7, 2), nullable=True)
    max_attempts = Column(Integer, default=1)
    shuffle_questions = Column(Boolean, default=False)
    shuffle_options = Column(Boolean, default=False)
    show_result_immediately = Column(Boolean, default=True)
    is_proctored = Column(Boolean, default=False)
    scheduled_start = Column(TIMESTAMP(timezone=True), nullable=True)
    scheduled_end = Column(TIMESTAMP(timezone=True), nullable=True)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id = Column(UUID(as_uuid=True), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    order_index = Column(Integer, nullable=False)
    marks_override = Column(Numeric(5, 2), nullable=True)

class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id = Column(UUID(as_uuid=True), ForeignKey("exams.id"), nullable=False)
    learner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status = Column(PgEnum(AttemptStatus, name="attempt_status", create_type=False), default=AttemptStatus.in_progress)
    started_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    submitted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    time_taken_seconds = Column(Integer, nullable=True)
    total_marks_obtained = Column(Numeric(7, 2), nullable=True)
    percentage = Column(Numeric(5, 2), nullable=True)
    is_passed = Column(Boolean, nullable=True)
    attempt_number = Column(Integer, default=1)
    final_trust_score = Column(Numeric(5, 2), nullable=True)
    is_flagged = Column(Boolean, default=False)
    proctor_notes = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

class AttemptResponse(Base):
    __tablename__ = "attempt_responses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id = Column(UUID(as_uuid=True), ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    selected_option_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)
    text_response = Column(Text, nullable=True)
    time_spent_seconds = Column(Integer, nullable=True)
    is_skipped = Column(Boolean, default=False)
    grade_status = Column(PgEnum(GradeStatus, name="grade_status", create_type=False), default=GradeStatus.pending)
    marks_obtained = Column(Numeric(5, 2), nullable=True)
    llm_score = Column(Numeric(5, 2), nullable=True)
    llm_feedback = Column(Text, nullable=True)
    llm_citation_highlights = Column(JSONB, nullable=True)
    llm_graded_at = Column(TIMESTAMP(timezone=True), nullable=True)
    llm_model_used = Column(String(100), nullable=True)
    manual_override_marks = Column(Numeric(5, 2), nullable=True)
    manual_override_reason = Column(Text, nullable=True)
    overridden_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    overridden_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
