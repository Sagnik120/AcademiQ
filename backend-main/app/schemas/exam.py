from pydantic import BaseModel, field_validator
from typing import Optional, List, Any
from enum import Enum
from datetime import datetime

class ExamTypeEnum(str, Enum):
    quiz = "quiz"
    test = "test"

class ExamStatusEnum(str, Enum):
    draft = "draft"
    scheduled = "scheduled"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"

# ── Exam ──────────────────────────────────────────
class ExamCreateRequest(BaseModel):
    course_id: str
    title: str
    description: Optional[str] = None
    exam_type: ExamTypeEnum
    instructions: Optional[str] = None
    duration_minutes: int
    passing_marks: Optional[float] = None
    max_attempts: int = 1
    shuffle_questions: bool = False
    shuffle_options: bool = False
    show_result_immediately: bool = True
    is_proctored: bool = False
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None

    @field_validator("duration_minutes")
    @classmethod
    def valid_duration(cls, v):
        if v < 1:
            raise ValueError("Duration must be at least 1 minute")
        return v

class ExamUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    duration_minutes: Optional[int] = None
    passing_marks: Optional[float] = None
    max_attempts: Optional[int] = None
    shuffle_questions: Optional[bool] = None
    shuffle_options: Optional[bool] = None
    show_result_immediately: Optional[bool] = None
    is_proctored: Optional[bool] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None

class ExamResponse(BaseModel):
    id: str
    course_id: str
    educator_id: str
    title: str
    description: Optional[str] = None
    exam_type: str
    status: str
    duration_minutes: int
    total_marks: Optional[float] = None
    passing_marks: Optional[float] = None
    max_attempts: int
    shuffle_questions: bool
    shuffle_options: bool
    show_result_immediately: bool
    is_proctored: bool
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None

# ── Exam Questions ────────────────────────────────
class AddQuestionRequest(BaseModel):
    question_id: str
    order_index: int
    marks_override: Optional[float] = None

class ExamQuestionResponse(BaseModel):
    id: str
    exam_id: str
    question_id: str
    order_index: int
    marks_override: Optional[float] = None

# ── Attempt ───────────────────────────────────────
class QuestionForAttempt(BaseModel):
    id: str
    question_type: str
    question_text: str
    marks: float
    negative_marks: float
    order_index: int
    options: Optional[List[dict]] = None  # for mcq/msq, no is_correct shown

class AttemptStartResponse(BaseModel):
    attempt_id: str
    exam_id: str
    duration_minutes: int
    started_at: datetime
    questions: List[QuestionForAttempt]

class SubmitResponseRequest(BaseModel):
    question_id: str
    selected_option_ids: Optional[List[str]] = None
    text_response: Optional[str] = None
    time_spent_seconds: Optional[int] = None
    is_skipped: bool = False

class AttemptResultResponse(BaseModel):
    attempt_id: str
    exam_id: str
    status: str
    total_marks_obtained: Optional[float] = None
    percentage: Optional[float] = None
    is_passed: Optional[bool] = None
    time_taken_seconds: Optional[int] = None
    responses: Optional[List[dict]] = None

class MessageResponse(BaseModel):
    message: str
