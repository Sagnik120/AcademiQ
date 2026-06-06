import uuid
from sqlalchemy import Column, String, Boolean, Enum as PgEnum, TIMESTAMP, Text, Integer, Numeric, SmallInteger, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
from app.database import Base
import enum

class QuestionType(str, enum.Enum):
    mcq = "mcq"
    msq = "msq"
    text = "text"

class Question(Base):
    __tablename__ = "questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    educator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=True)
    question_type = Column(PgEnum(QuestionType, name="question_type", create_type=False), nullable=False)
    question_text = Column(Text, nullable=False)
    question_image_url = Column(Text, nullable=True)
    marks = Column(Numeric(5, 2), nullable=False, default=1)
    negative_marks = Column(Numeric(5, 2), default=0)
    explanation = Column(Text, nullable=True)
    difficulty_level = Column(SmallInteger, nullable=True)
    discrimination_index = Column(Numeric(4, 3), nullable=True)
    difficulty_index = Column(Numeric(4, 3), nullable=True)
    total_attempts = Column(Integer, default=0)
    correct_attempts = Column(Integer, default=0)
    tags = Column(ARRAY(Text), nullable=True)
    is_deleted = Column(Boolean, default=False)
    is_ai_generated = Column(Boolean, default=False)
    # No FK here — generation_jobs model added later in GenAI module
    ai_generation_job_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

class QuestionOption(Base):
    __tablename__ = "question_options"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    option_text = Column(Text, nullable=False)
    option_image_url = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=False, default=False)
    order_index = Column(SmallInteger, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

class ReferenceAnswer(Base):
    __tablename__ = "reference_answers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), unique=True, nullable=False)
    reference_text = Column(Text, nullable=False)
    grading_rubric = Column(Text, nullable=True)
    max_marks = Column(Numeric(5, 2), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
