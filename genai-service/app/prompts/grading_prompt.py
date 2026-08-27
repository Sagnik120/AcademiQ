GRADING_PROMPT = """You are an expert university examiner grading a student's answer.

QUESTION:
{question}

STUDENT'S ANSWER:
{student_answer}

REFERENCE ANSWER (model answer by educator):
{reference_answer}

MAXIMUM MARKS: {max_marks}
{rubric_section}

GRADING INSTRUCTIONS:
- Evaluate the student's answer ONLY against the reference answer in the context of the question.
- Distribute marks approximately: 50% conceptual accuracy, 30% completeness, 20% clarity.
- For citation_highlights, quote EXACT phrases from the STUDENT'S ANSWER — do NOT paraphrase or invent text.
  If the student's answer is blank or irrelevant, leave both arrays empty.
- marks_awarded must be between 0 and {max_marks}. Do NOT exceed {max_marks}.
- percentage = (marks_awarded / {max_marks}) * 100, rounded to 2 decimal places.

"""


def build_grading_prompt(
    question: str,
    student_answer: str,
    reference_answer: str,
    max_marks: float,
    grading_rubric: str | None = None,
) -> str:
    rubric_section = ""
    if grading_rubric:
        rubric_section = f"\nADDITIONAL RUBRIC HINTS:\n{grading_rubric}\n"

    return GRADING_PROMPT.format(
        question=question,
        student_answer=student_answer,
        reference_answer=reference_answer,
        max_marks=max_marks,
        rubric_section=rubric_section,
    )
