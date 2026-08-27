import os
import logging
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from app.schemas import GenerateRequest, GenerateResponse, GeneratedQuestion, QuestionOption
from app.prompts.generation_prompt import build_generation_prompt

logger = logging.getLogger(__name__)

CHUNK_SIZE = 80_000
CHUNK_OVERLAP = 2_000


# Wrapper so with_structured_output returns a list of questions
class QuestionsOutput(BaseModel):
    questions: List[GeneratedQuestion]


def _get_chain():
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("No API key found. Set GEMINI_API_KEY in .env")

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.7,
        api_key=api_key,
    )

    structured_llm = llm.with_structured_output(QuestionsOutput)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert university question paper setter.
Generate exactly the number of questions requested.
MCQ: exactly 4 options, exactly 1 is_correct=true.
MSQ: 4-5 options, 2-3 is_correct=true.
Text: include a reference_answer.
difficulty_level must be 1-5. marks must be positive."""),
        ("human", """{prompt_body}"""),
    ])

    return prompt | structured_llm


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def _call_chain(prompt_body: str) -> QuestionsOutput:
    chain = _get_chain()
    return await chain.ainvoke({"prompt_body": prompt_body})


def _chunk_content(text: str) -> list[str]:
    if len(text) <= CHUNK_SIZE:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunks.append(text[start:end])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


async def generate_questions(request: GenerateRequest) -> GenerateResponse:
    chunks = _chunk_content(request.content)
    n_chunks = len(chunks)
    all_questions: list[GeneratedQuestion] = []
    skipped = 0

    for i, chunk in enumerate(chunks):
        mcq = request.mcq_count // n_chunks + (request.mcq_count % n_chunks if i == n_chunks - 1 else 0)
        msq = request.msq_count // n_chunks + (request.msq_count % n_chunks if i == n_chunks - 1 else 0)
        txt = request.text_count // n_chunks + (request.text_count % n_chunks if i == n_chunks - 1 else 0)
        if mcq == 0 and msq == 0 and txt == 0:
            continue

        prompt_body = build_generation_prompt(
            content=chunk,
            mcq_count=mcq,
            msq_count=msq,
            text_count=txt,
            difficulty_hint=request.difficulty_hint,
        )

        try:
            result: QuestionsOutput = await _call_chain(prompt_body)
            all_questions.extend(result.questions)
        except Exception as e:
            logger.error("Generation failed on chunk %d: %s", i, e)
            skipped += 1

    return GenerateResponse(
        questions=all_questions,
        generated_count=len(all_questions),
        skipped_count=skipped,
    )

