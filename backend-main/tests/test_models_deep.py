import uuid
import json
import sqlite3
import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from app.database import Base
from app.models import (
    User, UserRole,
    Course, Category, CourseSection, CourseContent, Enrollment,
    Question, QuestionOption, ReferenceAnswer, QuestionType,
    Exam, ExamQuestion, ExamAttempt, AttemptResponse,
    ProctorSession, ProctorAlert, AlertType, AlertSeverity,
    GenerationJob, GeneratedQuestion, GenerationStatus,
    LiveSession, Notification, NotificationType, AuditLog
)

# SQLite compatibility compilers for PostgreSQL-specific types during in-memory testing
sqlite3.register_adapter(dict, json.dumps)
sqlite3.register_adapter(list, json.dumps)

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(ARRAY, "sqlite")
def compile_array_sqlite(type_, compiler, **kw):
    return "JSON"

def _normalize_json(val):
    """Normalizes JSON string to Python structure if returned as text by SQLite."""
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return val
    return val

@pytest.fixture(scope="function")
def db_session():
    # Fresh in-memory SQLite database per test function for full test isolation
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


class TestSchemaRegistry:
    """Verifies that all required tables are mapped in SQLAlchemy metadata."""

    def test_all_expected_tables_registered(self):
        expected_tables = {
            "users", "courses", "categories", "course_sections", "course_contents", "enrollments",
            "questions", "question_options", "reference_answers",
            "exams", "exam_questions", "exam_attempts", "attempt_responses",
            "proctor_sessions", "proctor_alerts",
            "generation_jobs", "generated_questions",
            "live_sessions", "notifications", "audit_logs"
        }
        registered_tables = set(Base.metadata.tables.keys())
        missing = expected_tables - registered_tables
        assert not missing, f"Missing tables in metadata registry: {missing}"
        assert len(registered_tables) >= len(expected_tables)


class TestProctoringModels:
    """Deep boundary and integrity tests for ProctorSession and ProctorAlert."""

    def test_proctor_session_creation_and_defaults(self, db_session):
        attempt_id = uuid.uuid4()
        session = ProctorSession(
            attempt_id=attempt_id,
            initial_trust_score=100.0,
            is_flagged=False
        )
        db_session.add(session)
        db_session.commit()

        assert session.id is not None
        assert float(session.initial_trust_score) == 100.0
        assert session.final_trust_score is None
        assert session.is_flagged is False
        assert session.total_alerts_count == 0
        assert session.started_at is not None

    def test_proctor_session_trust_score_boundaries(self, db_session):
        # Boundary cases: 100.0, 50.5, 0.0, negative score
        for score in [100.0, 50.5, 0.0, -10.0]:
            attempt_id = uuid.uuid4()
            session = ProctorSession(
                attempt_id=attempt_id,
                initial_trust_score=score,
                final_trust_score=score
            )
            db_session.add(session)
            db_session.commit()
            assert float(session.final_trust_score) == float(score)

    def test_proctor_alert_all_enums_and_severities(self, db_session):
        attempt_id = uuid.uuid4()
        alert_types = list(AlertType)
        severities = list(AlertSeverity)

        for i, a_type in enumerate(alert_types):
            sev = severities[i % len(severities)]
            alert = ProctorAlert(
                attempt_id=attempt_id,
                alert_type=a_type,
                severity=sev,
                confidence=0.985,
                trust_deduction=5.00,
                timestamp=1700000000.1234
            )
            db_session.add(alert)
        db_session.commit()

        count = db_session.query(ProctorAlert).filter_by(attempt_id=attempt_id).count()
        assert count == len(alert_types)

    def test_proctor_alert_extreme_strings_and_urls(self, db_session):
        attempt_id = uuid.uuid4()
        # 5,000 char snapshot URL
        long_url = "https://res.cloudinary.com/test/image/upload/v1/" + ("a" * 5000) + ".jpg"
        alert = ProctorAlert(
            attempt_id=attempt_id,
            alert_type=AlertType.head_turn_severe,
            severity=AlertSeverity.high,
            snapshot_url=long_url,
            trust_deduction=5.0
        )
        db_session.add(alert)
        db_session.commit()
        assert alert.snapshot_url == long_url


class TestGenerationModels:
    """Deep boundary and payload tests for GenerationJob and GeneratedQuestion."""

    def test_generation_job_lifecycle_statuses(self, db_session):
        educator_id = uuid.uuid4()
        for status in GenerationStatus:
            job = GenerationJob(
                educator_id=educator_id,
                status=status,
                source_file_name="lecture_notes_ch1.pdf",
                mcq_count=10,
                msq_count=5,
                text_count=2,
                total_generated=17
            )
            db_session.add(job)
        db_session.commit()

        jobs = db_session.query(GenerationJob).filter_by(educator_id=educator_id).all()
        assert len(jobs) == len(list(GenerationStatus))

    def test_generated_question_complex_jsonb_and_unicode(self, db_session):
        job_id = uuid.uuid4()
        
        # Deeply nested complex options payload with unicode and math symbols
        complex_options = [
            {"id": "opt1", "text": "Einstein's E = mc² formula ⚛️", "is_correct": True, "details": {"tag": "physics"}},
            {"id": "opt2", "text": "Newton's F = ma force equation", "is_correct": False, "details": {"tag": "classical"}},
            {"id": "opt3", "text": "None of the above: ∅", "is_correct": False, "details": {}},
        ]
        
        # Very long text (10,000 characters)
        long_question_text = "Analyze the following system: " + ("Quantum entanglement principles. " * 300)

        q = GeneratedQuestion(
            job_id=job_id,
            question_type="mcq",
            question_text=long_question_text,
            options_json=complex_options,
            reference_answer="Comprehensive explanation with mathematical proof.",
            difficulty_level=4,
            marks=5.00
        )
        db_session.add(q)
        db_session.commit()

        fetched = db_session.query(GeneratedQuestion).filter_by(id=q.id).one()
        assert _normalize_json(fetched.options_json) == complex_options
        assert len(fetched.question_text) == len(long_question_text)
        assert fetched.difficulty_level == 4
        assert fetched.is_approved is False

    def test_generated_question_empty_and_minimal_payloads(self, db_session):
        job_id = uuid.uuid4()
        # Text question with empty options and empty explanation
        q = GeneratedQuestion(
            job_id=job_id,
            question_type="text",
            question_text="What is Backpropagation?",
            options_json=None,
            reference_answer="Algorithm for training neural networks.",
            explanation=None
        )
        db_session.add(q)
        db_session.commit()

        fetched = db_session.query(GeneratedQuestion).filter_by(id=q.id).one()
        assert fetched.options_json is None
        assert fetched.explanation is None


class TestLiveSessionAndNotifications:
    """Boundary tests for LiveSession, Notification, and AuditLog."""

    def test_live_session_room_id_and_special_chars(self, db_session):
        course_id = uuid.uuid4()
        educator_id = uuid.uuid4()
        room_id = f"room-live-bio101-{uuid.uuid4()}"
        
        session = LiveSession(
            course_id=course_id,
            educator_id=educator_id,
            room_id=room_id,
            title="🧬 Advanced Molecular Genetics Live Q&A",
            description="Discussion on CRISPR-Cas9 mechanisms and off-target effects."
        )
        db_session.add(session)
        db_session.commit()

        fetched = db_session.query(LiveSession).filter_by(room_id=room_id).one()
        assert fetched.is_active is False
        assert "CRISPR" in fetched.description
        assert "🧬" in fetched.title

    def test_notification_types_and_unread_filters(self, db_session):
        user_id = uuid.uuid4()
        for n_type in NotificationType:
            n = Notification(
                user_id=user_id,
                title=f"Notification: {n_type.value}",
                message="Your action has completed successfully.",
                notification_type=n_type,
                is_read=False,
                action_url=f"/exams/results/{uuid.uuid4()}"
            )
            db_session.add(n)
        db_session.commit()

        unread_count = db_session.query(Notification).filter_by(user_id=user_id, is_read=False).count()
        assert unread_count == len(list(NotificationType))

    def test_audit_log_arbitrary_json_and_ip_formats(self, db_session):
        user_id = uuid.uuid4()
        test_ips = ["127.0.0.1", "192.168.1.100", "2001:0db8:85a3:0000:0000:8a2e:0370:7334", "::1"]
        
        for ip in test_ips:
            log = AuditLog(
                user_id=user_id,
                action="USER_LOGIN_MFA",
                resource_type="AUTH",
                resource_id=str(user_id),
                details={"mfa_method": "totp", "user_agent": "Mozilla/5.0", "attempt": 1},
                ip_address=ip
            )
            db_session.add(log)
        db_session.commit()

        logs = db_session.query(AuditLog).filter_by(user_id=user_id).all()
        assert len(logs) == len(test_ips)
        assert _normalize_json(logs[0].details)["mfa_method"] == "totp"


class TestForeignKeyCascades:
    """Verifies foreign key cascade declarations across tables."""

    def test_cascade_delete_rules_defined(self):
        # ProctorAlert -> ProctorSession foreign key delete rule
        proctor_alert_fks = Base.metadata.tables["proctor_alerts"].foreign_keys
        session_fk = next(fk for fk in proctor_alert_fks if fk.target_fullname == "proctor_sessions.id")
        assert session_fk.ondelete.upper() == "CASCADE"

        # GeneratedQuestion -> GenerationJob foreign key delete rule
        gen_q_fks = Base.metadata.tables["generated_questions"].foreign_keys
        job_fk = next(fk for fk in gen_q_fks if fk.target_fullname == "generation_jobs.id")
        assert job_fk.ondelete.upper() == "CASCADE"

        # Notification -> User foreign key delete rule
        notification_fks = Base.metadata.tables["notifications"].foreign_keys
        user_fk = next(fk for fk in notification_fks if fk.target_fullname == "users.id")
        assert user_fk.ondelete.upper() == "CASCADE"
