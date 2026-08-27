import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from app.schemas import (
    GradeRequest, GradeResponse,
    CitationHighlights, CitationItem,
    RubricBreakdown, RubricScore,
)

logger = logging.getLogger(__name__)


def _get_chain():
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("No API key found. Set GEMINI_API_KEY in .env")

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.1,
        api_key=api_key,          # correct param name
    )

    # Structured output — returns GradeResponse directly, zero JSON parsing
    structured_llm = llm.with_structured_output(GradeResponse)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert university examiner.
Grade the student's answer against the reference answer.
Split marks: 50% conceptual accuracy, 30% completeness, 20% clarity.
For citation_highlights, quote EXACT phrases from the student's answer only.
marks_awarded must be between 0 and {max_marks}."""),
        ("human", """Question: {question}

Student Answer: {student_answer}

Reference Answer: {reference_answer}

Max Marks: {max_marks}
{rubric_section}"""),
    ])

    return prompt | structured_llm


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def _call_chain(question, student_answer, reference_answer, max_marks, rubric_section):
    chain = _get_chain()
    return await chain.ainvoke({
        "question": question,
        "student_answer": student_answer,
        "reference_answer": reference_answer,
        "max_marks": max_marks,
        "rubric_section": rubric_section,
    })


async def grade_answer(request: GradeRequest) -> GradeResponse:
    rubric_section = f"Additional rubric: {request.grading_rubric}" if request.grading_rubric else ""

    result: GradeResponse = await _call_chain(
        question=request.question,
        student_answer=request.student_answer,
        reference_answer=request.reference_answer,
        max_marks=request.max_marks,
        rubric_section=rubric_section,
    )

    # Safety clamps
    result.marks_awarded = max(0.0, min(result.marks_awarded, request.max_marks))
    result.percentage = round((result.marks_awarded / request.max_marks) * 100, 2) if request.max_marks else 0.0

    return result