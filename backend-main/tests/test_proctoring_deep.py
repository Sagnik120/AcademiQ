import uuid
import asyncio
import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import User, UserRole
from app.models.course import Course
from app.models.exam import Exam, ExamType, ExamAttempt, AttemptStatus
from app.models.proctor import ProctorSession
from app.services.proctor_service import (
    init_proctor_session,
    get_trust_score,
    process_proctor_frame,
    end_proctor_session,
    _in_memory_trust
)

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
def sample_attempt(db_session):
    learner = User(email=f"learner_{uuid.uuid4()}@test.com", password_hash="hash", role=UserRole.learner, first_name="A", last_name="B")
    educator = User(email=f"educator_{uuid.uuid4()}@test.com", password_hash="hash", role=UserRole.educator, first_name="C", last_name="D")
    db_session.add_all([learner, educator])
    db_session.flush()

    course = Course(educator_id=educator.id, title="Proctor Course", slug=f"proctor-{uuid.uuid4()}")
    db_session.add(course)
    db_session.flush()

    exam = Exam(course_id=course.id, educator_id=educator.id, title="Proctored Test", exam_type=ExamType.test, duration_minutes=30)
    db_session.add(exam)
    db_session.flush()

    attempt = ExamAttempt(exam_id=exam.id, learner_id=learner.id, status=AttemptStatus.in_progress)
    db_session.add(attempt)
    db_session.commit()
    return attempt


class TestProctoringDeep:

    def test_session_init_starts_at_100(self, db_session, sample_attempt):
        async def _run():
            attempt_id = str(sample_attempt.id)
            async_db = MockAsyncSession(db_session)

            session = await init_proctor_session(attempt_id, async_db, redis_client=None)

            assert float(session.initial_trust_score) == 100.0
            assert session.is_flagged is False
            assert session.total_alerts_count == 0

            score = await get_trust_score(attempt_id, redis_client=None)
            assert score == 100.0

        asyncio.run(_run())

    def test_sequential_trust_score_deductions(self, db_session, sample_attempt):
        async def _run():
            attempt_id = str(sample_attempt.id)
            _in_memory_trust[attempt_id] = 100.0

            sess = ProctorSession(attempt_id=sample_attempt.id, initial_trust_score=100.0)
            db_session.add(sess)
            db_session.commit()

            async_db = MockAsyncSession(db_session)

            # 1. Simulate head_turn_severe (-5.0) -> 100 - 5 = 95.0
            with patch("httpx.AsyncClient.post") as mock_post:
                mock_post.return_value = AsyncMock(status_code=200, json=lambda: {
                    "alert_type": "head_turn_severe", "severity": "high", "confidence": 0.99
                })
                res1 = await process_proctor_frame(attempt_id, "b64frame", None, async_db, redis_client=None)
                assert res1["current_trust_score"] == 95.0
                assert res1["is_flagged"] is False

            # 2. Simulate absent (-8.0) -> 95 - 8 = 87.0
            with patch("httpx.AsyncClient.post") as mock_post:
                mock_post.return_value = AsyncMock(status_code=200, json=lambda: {
                    "alert_type": "absent", "severity": "high", "confidence": 0.95
                })
                res2 = await process_proctor_frame(attempt_id, "b64frame", None, async_db, redis_client=None)
                assert res2["current_trust_score"] == 87.0
                assert res2["is_flagged"] is False

            # 3. Simulate multiple_face (-10.0) -> 87 - 10 = 77.0
            with patch("httpx.AsyncClient.post") as mock_post:
                mock_post.return_value = AsyncMock(status_code=200, json=lambda: {
                    "alert_type": "multiple_face", "severity": "critical", "confidence": 0.92
                })
                res3 = await process_proctor_frame(attempt_id, "b64frame", None, async_db, redis_client=None)
                assert res3["current_trust_score"] == 77.0
                assert res3["is_flagged"] is False

        asyncio.run(_run())

    def test_auto_flagging_threshold_and_floor_at_zero(self, db_session, sample_attempt):
        async def _run():
            attempt_id = str(sample_attempt.id)
            _in_memory_trust[attempt_id] = 65.0

            sess = ProctorSession(attempt_id=sample_attempt.id, initial_trust_score=100.0, is_flagged=False)
            db_session.add(sess)
            db_session.commit()

            async_db = MockAsyncSession(db_session)

            # Trigger absent (-8.0) -> Drops from 65.0 to 57.0 (below 60.0 threshold)
            with patch("httpx.AsyncClient.post") as mock_post:
                mock_post.return_value = AsyncMock(status_code=200, json=lambda: {
                    "alert_type": "absent", "severity": "high", "confidence": 0.98
                })
                res = await process_proctor_frame(attempt_id, "b64frame", None, async_db, redis_client=None)
                assert res["current_trust_score"] == 57.0
                assert res["is_flagged"] is True
                assert sess.is_flagged is True

            # Now simulate deduction below zero -> must floor at 0.0
            _in_memory_trust[attempt_id] = 5.0
            with patch("httpx.AsyncClient.post") as mock_post:
                mock_post.return_value = AsyncMock(status_code=200, json=lambda: {
                    "alert_type": "absent_extended", "severity": "critical", "confidence": 1.0
                })
                res_floor = await process_proctor_frame(attempt_id, "b64frame", None, async_db, redis_client=None)
                assert res_floor["current_trust_score"] == 0.0

        asyncio.run(_run())

    def test_end_session_syncs_score_to_exam_attempt(self, db_session, sample_attempt):
        async def _run():
            attempt_id = str(sample_attempt.id)
            _in_memory_trust[attempt_id] = 82.5

            sess = ProctorSession(attempt_id=sample_attempt.id, initial_trust_score=100.0, is_flagged=True)
            db_session.add(sess)
            db_session.commit()

            async_db = MockAsyncSession(db_session)

            ended_session = await end_proctor_session(attempt_id, async_db, redis_client=None)

            assert float(ended_session.final_trust_score) == 82.5
            assert ended_session.ended_at is not None
            assert float(sample_attempt.final_trust_score) == 82.5
            assert sample_attempt.is_flagged is True

        asyncio.run(_run())

    def test_resilience_when_ml_service_offline(self, db_session, sample_attempt):
        async def _run():
            attempt_id = str(sample_attempt.id)
            _in_memory_trust[attempt_id] = 95.0

            sess = ProctorSession(attempt_id=sample_attempt.id, initial_trust_score=100.0)
            db_session.add(sess)
            db_session.commit()

            async_db = MockAsyncSession(db_session)

            # Simulate connection error to ML service
            with patch("httpx.AsyncClient.post", side_effect=Exception("Connection refused")):
                res = await process_proctor_frame(attempt_id, "b64frame", None, async_db, redis_client=None)
                # Must not crash! Score maintained safely
                assert res["current_trust_score"] == 95.0
                assert res["alert_type"] is None

        asyncio.run(_run())
