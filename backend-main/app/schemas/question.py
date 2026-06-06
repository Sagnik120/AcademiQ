from pydantic import BaseModel, field_validator
from typing import Optional, List
from enum import Enum

class QuestionTypeEnum(str, Enum):
    mcq = "mcq"
    msq = "msq"
    text = "text"

class OptionCreate(BaseModel):
    option_text: str
    is_correct: bool = False
    order_index: int

class OptionResponse(BaseModel):
    id: str
    option_text: str
    is_correct: bool
    order_index: int
    class Config:
        from_attributes = True

class QuestionCreateRequest(BaseModel):
    question_type: QuestionTypeEnum
    question_text: str
    marks: float = 1.0
    negative_marks: float = 0.0
    explanation: Optional[str] = None
    difficulty_level: Optional[int] = None
    tags: Optional[List[str]] = None
    course_id: Optional[str] = None
    options: Optional[List[OptionCreate]] = None  # for mcq/msq

    @field_validator("question_text")
    @classmethod
    def text_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Question text cannot be empty")
        return v.strip()

    @field_validator("difficulty_level")
    @classmethod
    def valid_difficulty(cls, v):
        if v is not None and not (1 <= v <= 5):
            raise ValueError("Difficulty must be between 1 and 5")
        return v

class QuestionUpdateRequest(BaseModel):
    question_text: Optional[str] = None
    marks: Optional[float] = None
    negative_marks: Optional[float] = None
    explanation: Optional[str] = None
    difficulty_level: Optional[int] = None
    tags: Optional[List[str]] = None

class ReferenceAnswerCreate(BaseModel):
    reference_text: str
    grading_rubric: Optional[str] = None
    max_marks: float

class ReferenceAnswerResponse(BaseModel):
    id: str
    question_id: str
    reference_text: str
    grading_rubric: Optional[str] = None
    max_marks: float
    class Config:
        from_attributes = True

class QuestionResponse(BaseModel):
    id: str
    educator_id: str
    course_id: Optional[str] = None
    question_type: str
    question_text: str
    marks: float
    negative_marks: float
    explanation: Optional[str] = None
    difficulty_level: Optional[int] = None
    tags: Optional[List[str]] = None
    is_ai_generated: bool
    options: Optional[List[OptionResponse]] = None
    reference_answer: Optional[ReferenceAnswerResponse] = None
    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    message: str
