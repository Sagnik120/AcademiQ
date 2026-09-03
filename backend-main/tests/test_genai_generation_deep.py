import uuid
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import User, UserRole
from app.models.course import Course
from app.models.generation import GenerationJob, GeneratedQuestion, GenerationStatus
from app.models.question import Question, QuestionOption, ReferenceAnswer, QuestionType
from app.services.generation_service import process_generation_job, approve_generated_question


class MockAsyncSession:
    """Bridges synchronous SQLite test session to the AsyncSession interface."""
    def __init__(self, sync_session):
        self._sync = sync_session

    async def execute(self, statement):
        return self._sync.execute(statement)

    async def commit(self):
        self._sync.commit()

    async def flush(self):
        self._sync.flush()

    async def refresh(self, instance):
        self._sync.refresh(instance)

    def add(self, instance):
        self._sync.add(instance)


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def sample_job_data(db_session):
    educator = User(email=f"prof_{uuid.uuid4()}@univ.edu", password_hash="hash", role=UserRole.educator, first_name="Alan", last_name="Turing")
    db_session.add(educator)
    db_session.flush()

    course = Course(educator_id=educator.id, title="Quantum Computing", slug=f"qc-{uuid.uuid4()}")
    db_session.add(course)
    db_session.flush()

    job = GenerationJob(
        educator_id=educator.id,
        course_id=course.id,
        status=GenerationStatus.pending,
        source_file_name="syllabus_quantum.pdf",
        mcq_count=2,
        msq_count=1,
        text_count=1
    )
    db_session.add(job)
    db_session.commit()

    return {
        "educator": educator,
        "course": course,
        "job": job
    }


class TestGenAIGenerationDeep:

    def test_generation_from_raw_text_success(self, db_session, sample_job_data):
        async def _run():
            job = sample_job_data["job"]
            async_db = MockAsyncSession(db_session)

            mock_response_payload = {
                "generated_count": 3,
                "skipped_count": 0,
                "questions": [
                    {
                        "type": "mcq",
                        "question_text": "What is the primary unit of quantum information?",
                        "difficulty_level": 2,
                        "marks": 1.0,
                        "options": [
                            {"option_text": "Bit", "is_correct": False},
                            {"option_text": "Qubit", "is_correct": True}
                        ],
                        "explanation": "A qubit is the basic unit of quantum information."
                    },
                    {
                        "type": "msq",
                        "question_text": "Which of the following are quantum phenomena?",
                        "difficulty_level": 4,
                        "marks": 2.0,
                        "options": [
                            {"option_text": "Superposition", "is_correct": True},
                            {"option_text": "Entanglement", "is_correct": True},
                            {"option_text": "Binary clocking", "is_correct": False}
                        ],
                        "explanation": "Superposition and Entanglement are pure quantum mechanics phenomena."
                    },
                    {
                        "type": "text",
                        "question_text": "Explain Shor's algorithm and its significance to modern RSA encryption.",
                        "difficulty_level": 5,
                        "marks": 5.0,
                        "reference_answer": "Shor's algorithm factors integers in polynomial time.",
                        "explanation": "Crucial for post-quantum cryptographic security."
                    }
                ]
            }

            mock_gen_resp = MagicMock()
            mock_gen_resp.status_code = 200
            mock_gen_resp.json.return_value = mock_response_payload

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_gen_resp

                await process_generation_job(
                    job_id=str(job.id),
                    file_b64=None,
                    raw_text="Quantum mechanics principles: Qubits, Superposition, Entanglement, and Shor's algorithm.",
                    difficulty_hint="intermediate",
                    session_override=async_db
                )

            # Verify job status
            db_session.refresh(job)
            assert job.status == GenerationStatus.completed
            assert job.total_generated == 3
            assert job.error_message is None

            # Verify saved candidate questions
            candidates = db_session.execute(select(GeneratedQuestion).where(GeneratedQuestion.job_id == job.id)).scalars().all()
            assert len(candidates) == 3
            types = [c.question_type for c in candidates]
            assert "mcq" in types
            assert "msq" in types
            assert "text" in types

            # Check MCQ options
            mcq_q = next(c for c in candidates if c.question_type == "mcq")
            assert len(mcq_q.options_json) == 2
            assert mcq_q.options_json[1]["option_text"] == "Qubit"
            assert mcq_q.options_json[1]["is_correct"] is True

            # Check Text reference answer
            text_q = next(c for c in candidates if c.question_type == "text")
            assert "Shor's algorithm" in text_q.reference_answer

        asyncio.run(_run())

    def test_generation_with_pdf_extraction_pipeline(self, db_session, sample_job_data):
        async def _run():
            job = sample_job_data["job"]
            async_db = MockAsyncSession(db_session)

            mock_pdf_resp = MagicMock()
            mock_pdf_resp.status_code = 200
            mock_pdf_resp.json.return_value = {
                "text": "Extracted Syllabus: Quantum Gates and Quantum Key Distribution (BB84 protocol).",
                "page_count": 3,
                "extraction_method": "pdfplumber",
                "char_count": 85
            }

            mock_gen_resp = MagicMock()
            mock_gen_resp.status_code = 200
            mock_gen_resp.json.return_value = {
                "generated_count": 1,
                "skipped_count": 0,
                "questions": [
                    {
                        "type": "mcq",
                        "question_text": "What protocol is used for Quantum Key Distribution?",
                        "difficulty_level": 3,
                        "marks": 1.0,
                        "options": [
                            {"option_text": "BB84", "is_correct": True},
                            {"option_text": "HTTP", "is_correct": False}
                        ],
                        "explanation": "BB84 is the foundational QKD protocol."
                    }
                ]
            }

            # First post call -> extract-pdf, second post call -> generate-questions
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.side_effect = [mock_pdf_resp, mock_gen_resp]

                await process_generation_job(
                    job_id=str(job.id),
                    file_b64="fake-base64-pdf-content",
                    raw_text=None,
                    difficulty_hint="advanced",
                    session_override=async_db
                )

            db_session.refresh(job)
            assert job.status == GenerationStatus.completed
            assert job.total_generated == 1

        asyncio.run(_run())

    def test_approve_candidate_into_question_bank(self, db_session, sample_job_data):
        async def _run():
            job = sample_job_data["job"]
            educator = sample_job_data["educator"]
            async_db = MockAsyncSession(db_session)

            gen_q = GeneratedQuestion(
                job_id=job.id,
                question_type="mcq",
                question_text="What is quantum entanglement?",
                options_json=[
                    {"option_text": "Correlated quantum states", "is_correct": True},
                    {"option_text": "Classical electromagnetic waves", "is_correct": False}
                ],
                explanation="Non-local quantum correlation.",
                difficulty_level=3,
                marks=2.0,
                is_approved=False
            )
            db_session.add(gen_q)
            db_session.commit()

            # Approve question
            res = await approve_generated_question(
                job_id=str(job.id),
                question_id=str(gen_q.id),
                educator_id=str(educator.id),
                db=async_db
            )

            assert "successfully approved" in res["message"].lower()
            assert res["generated_question_id"] == str(gen_q.id)

            # Verify in GeneratedQuestion record
            db_session.refresh(gen_q)
            assert gen_q.is_approved is True
            assert gen_q.approved_question_id is not None

            # Verify row created in primary Question Bank
            new_q = db_session.execute(select(Question).where(Question.id == gen_q.approved_question_id)).scalar_one_or_none()
            assert new_q is not None
            assert new_q.question_text == "What is quantum entanglement?"
            assert new_q.is_ai_generated is True
            assert new_q.ai_generation_job_id == job.id
            assert float(new_q.marks) == 2.0

            # Verify options created in QuestionOption table
            options = db_session.execute(select(QuestionOption).where(QuestionOption.question_id == new_q.id)).scalars().all()
            assert len(options) == 2
            correct = next(opt for opt in options if opt.is_correct)
            assert correct.option_text == "Correlated quantum states"

        asyncio.run(_run())

    def test_empty_content_fails_gracefully(self, db_session, sample_job_data):
        async def _run():
            job = sample_job_data["job"]
            async_db = MockAsyncSession(db_session)

            await process_generation_job(
                job_id=str(job.id),
                file_b64=None,
                raw_text="", # Empty boundary
                difficulty_hint=None,
                session_override=async_db
            )

            db_session.refresh(job)
            assert job.status == GenerationStatus.failed
            assert "no readable" in job.error_message.lower()

        asyncio.run(_run())

    def test_resilience_when_genai_service_returns_500(self, db_session, sample_job_data):
        async def _run():
            job = sample_job_data["job"]
            async_db = MockAsyncSession(db_session)

            mock_fail_resp = MagicMock()
            mock_fail_resp.status_code = 500
            mock_fail_resp.text = "Internal Server Error: Gemini rate limit exceeded"

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_fail_resp

                await process_generation_job(
                    job_id=str(job.id),
                    file_b64=None,
                    raw_text="Machine learning models and gradient descent.",
                    difficulty_hint=None,
                    session_override=async_db
                )

            db_session.refresh(job)
            assert job.status == GenerationStatus.failed
            assert "500" in job.error_message

        asyncio.run(_run())

    def test_unauthorized_educator_approval_blocked(self, db_session, sample_job_data):
        async def _run():
            job = sample_job_data["job"]
            async_db = MockAsyncSession(db_session)

            gen_q = GeneratedQuestion(
                job_id=job.id,
                question_type="text",
                question_text="Test question",
                marks=1.0
            )
            db_session.add(gen_q)
            db_session.commit()

            unauthorized_educator_id = str(uuid.uuid4())

            with pytest.raises(HTTPException) as exc_info:
                await approve_generated_question(
                    job_id=str(job.id),
                    question_id=str(gen_q.id),
                    educator_id=unauthorized_educator_id,
                    db=async_db
                )
            assert exc_info.value.status_code == 403

        asyncio.run(_run())
