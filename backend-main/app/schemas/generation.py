from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime

class GenerateQuestionsRequest(BaseModel):
    content: Optional[str] = Field(None, description="Direct syllabus or lecture text")
    file_bytes_base64: Optional[str] = Field(None, description="Base64 encoded PDF file bytes")
    source_file_name: Optional[str] = Field(None, description="Original filename of the syllabus")
    course_id: Optional[str] = Field(None, description="Target course ID for the questions")
    mcq_count: int = Field(default=5, ge=0, le=20)
    msq_count: int = Field(default=3, ge=0, le=20)
    text_count: int = Field(default=2, ge=0, le=10)
    difficulty_hint: Optional[str] = Field(None, description="beginner | intermediate | advanced")

class GenerationJobResponse(BaseModel):
    job_id: str
    status: str
    source_file_name: Optional[str] = None
    mcq_count: int
    msq_count: int
    text_count: int
    total_generated: int
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

class QuestionOptionSchema(BaseModel):
    option_text: str
    is_correct: bool

class GeneratedQuestionResponse(BaseModel):
    id: str
    job_id: str
    question_type: str
    question_text: str
    options: Optional[List[dict]] = None
    reference_answer: Optional[str] = None
    explanation: Optional[str] = None
    difficulty_level: int
    marks: float
    is_approved: bool
    approved_question_id: Optional[str] = None
    created_at: datetime

class ApproveQuestionResponse(BaseModel):
    message: str
    generated_question_id: str
    approved_question_id: str
