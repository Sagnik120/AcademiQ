import uuid
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import User, UserRole
from app.models.course import Course
from app.models.question import Question, ReferenceAnswer, QuestionType
from app.models.exam import (
    Exam, ExamAttempt, AttemptResponse,
    ExamType, ExamStatus, AttemptStatus, GradeStatus
)
from app.services.grading_service import _grade_single_response


class MockAsyncSession:
    """Bridges synchronous SQLite test session to the AsyncSession interface."""
    def __init__(self, sync_session):
        self._sync = sync_session

    async def execute(self, statement):
        return self._sync.execute(statement)

    async def commit(self):
        self._sync.commit()

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
def sample_attempt_data(db_session):
    educator = User(email=f"educator_{uuid.uuid4()}@test.com", password_hash="hash", role=UserRole.educator, first_name="Dr", last_name="Smith")
    learner = User(email=f"learner_{uuid.uuid4()}@test.com", password_hash="hash", role=UserRole.learner, first_name="Jane", last_name="Doe")
    db_session.add_all([educator, learner])
    db_session.flush()

    course = Course(educator_id=educator.id, title="AI Systems", slug=f"ai-{uuid.uuid4()}")
    db_session.add(course)
    db_session.flush()

    exam = Exam(
        course_id=course.id, educator_id=educator.id, title="Midterm",
        exam_type=ExamType.test, status=ExamStatus.active, duration_minutes=60,
        total_marks=20.0, passing_marks=10.0
    )
    db_session.add(exam)
    db_session.flush()

    q_text = Question(
        educator_id=educator.id, course_id=course.id, question_type=QuestionType.text,
        question_text="Explain Gradient Descent and its variants.", marks=10.0
    )
    db_session.add(q_text)
    db_session.flush()

    ref = ReferenceAnswer(
        question_id=q_text.id,
        reference_text="Gradient Descent optimizes loss by taking steps in the direction of negative gradient.",
        grading_rubric="50% concept, 30% completeness, 20% clarity",
        max_marks=10.0
    )
    db_session.add(ref)
    db_session.flush()

    attempt = ExamAttempt(
        exam_id=exam.id, learner_id=learner.id, status=AttemptStatus.submitted
    )
    db_session.add(attempt)
    db_session.commit()

    return {
        "exam": exam,
        "question": q_text,
        "attempt": attempt,
        "learner": learner,
        "ref": ref
    }


class TestGenAIGradingDeep:

    def test_empty_answer_awards_zero_without_llm_call(self, db_session, sample_attempt_data):
        async def _run():
            attempt = sample_attempt_data["attempt"]
            q = sample_attempt_data["question"]

            resp = AttemptResponse(
                attempt_id=attempt.id,
                question_id=q.id,
                text_response="", # Empty string boundary
                grade_status=GradeStatus.pending
            )
            db_session.add(resp)
            db_session.commit()

            async_db = MockAsyncSession(db_session)
            awarded = await _grade_single_response(resp, AsyncMock(), async_db)

            assert awarded == 0.0
            assert resp.marks_obtained == 0.0
            assert resp.llm_score == 0.0
            assert resp.llm_feedback == "No answer provided."
            assert resp.grade_status == GradeStatus.graded

        asyncio.run(_run())

    def test_valid_grading_flow_with_citation_highlights(self, db_session, sample_attempt_data):
        async def _run():
            attempt = sample_attempt_data["attempt"]
            q = sample_attempt_data["question"]

            resp = AttemptResponse(
                attempt_id=attempt.id,
                question_id=q.id,
                text_response="Gradient descent computes gradients of the loss with respect to parameters and updates them.",
                grade_status=GradeStatus.pending
            )
            db_session.add(resp)
            db_session.commit()

            mock_gemini_response = {
                "marks_awarded": 8.5,
                "percentage": 85.0,
                "overall_feedback": "Strong explanation of the core optimization principle.",
                "citation_highlights": {
                    "earned_marks": ["computes gradients of the loss", "updates them"],
                    "lost_marks": ["did not mention mini-batch or momentum variants"]
                },
                "rubric_breakdown": {
                    "accuracy": {"score": 4.5, "max_score": 5.0, "feedback": "Accurate"},
                    "completeness": {"score": 2.0, "max_score": 3.0, "feedback": "Missing variants"},
                    "clarity": {"score": 2.0, "max_score": 2.0, "feedback": "Very clear"}
                },
                "model": "gemini-2.5-flash"
            }

            # Response is synchronous in HTTPX; post() is async
            mock_http_resp = MagicMock()
            mock_http_resp.status_code = 200
            mock_http_resp.json.return_value = mock_gemini_response

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_http_resp

            async_db = MockAsyncSession(db_session)
            awarded = await _grade_single_response(resp, mock_client, async_db)

            assert awarded == 8.5
            assert resp.marks_obtained == 8.5
            assert resp.llm_score == 8.5
            assert resp.llm_model_used == "gemini-2.5-flash"
            assert len(resp.llm_citation_highlights["earned_marks"]) == 2
            assert len(resp.llm_citation_highlights["lost_marks"]) == 1
            assert resp.grade_status == GradeStatus.graded

        asyncio.run(_run())

    def test_extreme_10k_char_answer_boundary(self, db_session, sample_attempt_data):
        async def _run():
            attempt = sample_attempt_data["attempt"]
            q = sample_attempt_data["question"]

            long_essay = "Optimization theory in machine learning: " + ("parameters are iteratively updated. " * 300)
            assert len(long_essay) > 10000

            resp = AttemptResponse(
                attempt_id=attempt.id,
                question_id=q.id,
                text_response=long_essay,
                grade_status=GradeStatus.pending
            )
            db_session.add(resp)
            db_session.commit()

            mock_http_resp = MagicMock()
            mock_http_resp.status_code = 200
            mock_http_resp.json.return_value = {
                "marks_awarded": 10.0,
                "overall_feedback": "Thorough and exhaustive answer.",
                "citation_highlights": {"earned_marks": ["Optimization theory"], "lost_marks": []},
                "model": "gemini-2.5-flash"
            }

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_http_resp

            async_db = MockAsyncSession(db_session)
            awarded = await _grade_single_response(resp, mock_client, async_db)

            assert awarded == 10.0
            assert resp.marks_obtained == 10.0

        asyncio.run(_run())

    def test_resilience_when_genai_service_fails(self, db_session, sample_attempt_data):
        async def _run():
            attempt = sample_attempt_data["attempt"]
            q = sample_attempt_data["question"]

            resp = AttemptResponse(
                attempt_id=attempt.id,
                question_id=q.id,
                text_response="SGD with mini batches.",
                grade_status=GradeStatus.pending
            )
            db_session.add(resp)
            db_session.commit()

            mock_http_resp = MagicMock()
            mock_http_resp.status_code = 500
            mock_http_resp.text = "Internal Server Error: Gemini rate limit exceeded"

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_http_resp

            async_db = MockAsyncSession(db_session)
            awarded = await _grade_single_response(resp, mock_client, async_db)

            # Retains pending status for future retry without crashing
            assert awarded == 0.0
            assert resp.grade_status == GradeStatus.pending

        asyncio.run(_run())
