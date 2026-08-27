GENERATION_PROMPT = """You are an expert question paper setter for a university exam.

CONTENT TO USE:
{content}

DIFFICULTY: {difficulty_hint}

TASK: Generate EXACTLY {mcq_count} MCQ, {msq_count} MSQ, and {text_count} text questions from the content above.
- If the content is too short for the full count, generate as many as the content supports.
- MCQ: exactly 4 options, exactly 1 is_correct=true.
- MSQ: 4 to 5 options, 2 to 3 is_correct=true.
- Text: include a reference_answer that an educator can use to grade student responses.
- difficulty_level: integer from 1 (easiest) to 5 (hardest), matching the difficulty hint.
- marks: a positive float appropriate to the question complexity.

"""


def build_generation_prompt(
    content: str,
    mcq_count: int,
    msq_count: int,
    text_count: int,
    difficulty_hint: str | None = None,
) -> str:
    difficulty = difficulty_hint or "intermediate"
    return GENERATION_PROMPT.format(
        content=content,
        mcq_count=mcq_count,
        msq_count=msq_count,
        text_count=text_count,
        difficulty_hint=difficulty,
    )
