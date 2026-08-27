from pydantic import BaseModel, Field
from typing import Optional


# ── Grading ──────────────────────────────────────────────────────────────────

class GradeRequest(BaseModel):
    question: str
    student_answer: str
    reference_answer: str
    max_marks: float
    grading_rubric: Optional[str] = None


class CitationItem(BaseModel):
    text: str           # exact phrase from student answer
    reason: str         # why it earned/lost marks
    marks: float


class CitationHighlights(BaseModel):
    earned_marks: list[CitationItem] = []
    lost_marks: list[CitationItem] = []


class RubricScore(BaseModel):
    score: float
    comment: str


class RubricBreakdown(BaseModel):
    conceptual_accuracy: RubricScore
    completeness: RubricScore
    clarity: RubricScore


class GradeResponse(BaseModel):
    marks_awarded: float
    percentage: float
    overall_feedback: str
    citation_highlights: CitationHighlights
    rubric_breakdown: RubricBreakdown


# ── Question Generation ───────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    content: str
    mcq_count: int = Field(default=5, ge=0, le=20)
    msq_count: int = Field(default=3, ge=0, le=20)
    text_count: int = Field(default=2, ge=0, le=10)
    difficulty_hint: Optional[str] = None  # "beginner" | "intermediate" | "advanced"


class QuestionOption(BaseModel):
    option_text: str
    is_correct: bool


class GeneratedQuestion(BaseModel):
    type: str                           # "mcq" | "msq" | "text"
    question_text: str
    marks: float
    difficulty_level: int               # 1-5
    options: Optional[list[QuestionOption]] = None
    reference_answer: Optional[str] = None


class GenerateResponse(BaseModel):
    questions: list[GeneratedQuestion]
    generated_count: int
    skipped_count: int


# ── PDF Extraction ────────────────────────────────────────────────────────────

class ExtractPDFRequest(BaseModel):
    file_bytes: str     # base64 encoded PDF


class ExtractPDFResponse(BaseModel):
    text: str
    page_count: int
    extraction_method: str  # "pypdf2" | "pdfplumber"
    char_count: int
