import uuid
import enum
from sqlalchemy import Column, String, Boolean, Enum as PgEnum, TIMESTAMP, Text, Integer, Numeric, SmallInteger, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.database import Base

class GenerationStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"

class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    educator_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    status = Column(PgEnum(GenerationStatus, name="generation_status", create_type=False), default=GenerationStatus.pending, nullable=False)
    source_file_name = Column(String(255), nullable=True)
    source_file_url = Column(Text, nullable=True)
    mcq_count = Column(Integer, default=0, nullable=False)
    msq_count = Column(Integer, default=0, nullable=False)
    text_count = Column(Integer, default=0, nullable=False)
    total_generated = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

class GeneratedQuestion(Base):
    __tablename__ = "generated_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    question_type = Column(String(20), nullable=False)
    question_text = Column(Text, nullable=False)
    options_json = Column(JSONB, nullable=True)
    reference_answer = Column(Text, nullable=True)
    explanation = Column(Text, nullable=True)
    difficulty_level = Column(SmallInteger, default=3, nullable=False)
    marks = Column(Numeric(5, 2), default=1.00, nullable=False)
    is_approved = Column(Boolean, default=False, nullable=False)
    approved_question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
