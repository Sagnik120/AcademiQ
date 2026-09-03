import os
import uuid
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import User, UserRole
from app.models.course import Course
from app.models.exam import Exam, ExamType
from app.models.proctor import ProctorSession
from app.models.audit import AuditLog
from app.models.notification import Notification, NotificationType
from app.models.live_session import LiveSession

from app.services.storage_service import upload_file_bytes, delete_file
from app.services.notification_service import create_notification
from app.services.live_session_service import WebRTCSignalingManager
from app.routers.admin import get_platform_stats, update_user_status
from app.schemas.admin import UserStatusUpdateRequest


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


class TestMilestone4Deep:

    # ── 1. Storage Tests ───────────────────────────────────────────────────────

    def test_storage_local_fallback_upload_and_delete(self):
        filename = f"sample_note_{uuid.uuid4().hex[:6]}.txt"
        content = b"Lecture 1: Introduction to AcademiQ platform."

        result = upload_file_bytes(content, filename, folder="test_docs")

        assert result["filename"] == filename
        assert result["size"] == len(content)
        assert "/uploads/test_docs/" in result["url"]

        # Verify file physically exists on disk
        local_path = os.path.join(os.getcwd(), "uploads", "test_docs", filename)
        assert os.path.exists(local_path)
        with open(local_path, "rb") as f:
            assert f.read() == content

        # Verify deletion cleans up file
        deleted = delete_file(result["public_id"])
        assert deleted is True
        assert not os.path.exists(local_path)

    # ── 2. Admin Management Tests ──────────────────────────────────────────────

    def test_admin_platform_stats_aggregation(self, db_session):
        async def _run():
            # Seed users
            admin = User(email=f"admin_{uuid.uuid4()}@test.com", password_hash="h", role=UserRole.admin, first_name="Super", last_name="Admin")
            learner = User(email=f"learn_{uuid.uuid4()}@test.com", password_hash="h", role=UserRole.learner, first_name="Bob", last_name="Lee")
            educator = User(email=f"edu_{uuid.uuid4()}@test.com", password_hash="h", role=UserRole.educator, first_name="Ada", last_name="Lovelace")
            db_session.add_all([admin, learner, educator])
            db_session.flush()

            # Seed course and exam
            course = Course(educator_id=educator.id, title="Quantum Computing", slug=f"qc-{uuid.uuid4()}")
            db_session.add(course)
            db_session.flush()

            exam = Exam(course_id=course.id, educator_id=educator.id, title="Final Exam", exam_type=ExamType.test, duration_minutes=60)
            db_session.add(exam)
            db_session.flush()

            # Seed proctor sessions (1 active, 1 flagged)
            sess1 = ProctorSession(attempt_id=uuid.uuid4(), initial_trust_score=100.0, is_flagged=False)
            sess2 = ProctorSession(attempt_id=uuid.uuid4(), initial_trust_score=50.0, is_flagged=True)
            db_session.add_all([sess1, sess2])
            db_session.commit()

            async_db = MockAsyncSession(db_session)
            stats = await get_platform_stats(current_user=admin, db=async_db)

            assert stats.total_users == 3
            assert stats.total_learners == 1
            assert stats.total_educators == 1
            assert stats.total_admins == 1
            assert stats.total_courses == 1
            assert stats.total_exams == 1
            assert stats.active_proctor_sessions == 2
            assert stats.flagged_proctor_sessions == 1

        asyncio.run(_run())

    def test_admin_user_status_toggling_with_audit_log(self, db_session):
        async def _run():
            admin = User(email=f"admin_{uuid.uuid4()}@test.com", password_hash="h", role=UserRole.admin, first_name="A", last_name="B")
            target = User(email=f"target_{uuid.uuid4()}@test.com", password_hash="h", role=UserRole.learner, first_name="T", last_name="U", is_active=True)
            db_session.add_all([admin, target])
            db_session.commit()

            mock_request = MagicMock()
            mock_request.client.host = "192.168.1.50"

            async_db = MockAsyncSession(db_session)
            res = await update_user_status(
                user_id=str(target.id),
                payload=UserStatusUpdateRequest(is_active=False),
                request=mock_request,
                current_user=admin,
                db=async_db
            )

            # Check user deactivated
            assert res.is_active is False
            db_session.refresh(target)
            assert target.is_active is False

            # Check audit log written
            audit = db_session.execute(select(AuditLog).where(AuditLog.resource_id == str(target.id))).scalar_one_or_none()
            assert audit is not None
            assert audit.action == "update_user_status"
            assert audit.ip_address == "192.168.1.50"
            assert audit.details["new_active_status"] is False

        asyncio.run(_run())

    # ── 3. Notification Tests ──────────────────────────────────────────────────

    def test_notification_creation_and_reading(self, db_session):
        async def _run():
            user = User(email=f"user_{uuid.uuid4()}@test.com", password_hash="h", role=UserRole.learner, first_name="N", last_name="T")
            db_session.add(user)
            db_session.commit()

            async_db = MockAsyncSession(db_session)

            # 1. Dispatch notification
            notif = await create_notification(
                user_id=str(user.id),
                title="Exam Results Released",
                message="Your score for Midterm 1 is now available.",
                notification_type="exam_graded",
                db=async_db
            )

            assert notif is not None
            assert notif.is_read is False
            assert notif.title == "Exam Results Released"
            assert notif.notification_type == NotificationType.exam_graded

            # 2. Mark as read
            notif.is_read = True
            await async_db.commit()

            db_session.refresh(notif)
            assert notif.is_read is True

        asyncio.run(_run())

    # ── 4. WebRTC Live Sessions Tests ──────────────────────────────────────────

    def test_webrtc_signaling_manager_peer_routing(self):
        async def _run():
            mgr = WebRTCSignalingManager()
            room_id = f"room_{uuid.uuid4().hex[:8]}"

            ws1 = AsyncMock()
            ws2 = AsyncMock()

            # Connect peer1 and peer2
            await mgr.connect(room_id, "peer1", ws1)
            await mgr.connect(room_id, "peer2", ws2)

            # Check ws1 received peer_joined notification for peer2
            ws1.send_json.assert_called_with({
                "type": "peer_joined",
                "peer_id": "peer2"
            })

            # Send targeted SDP offer from peer1 to peer2
            offer_payload = {
                "type": "offer",
                "sdp": "v=0\r\no=...",
                "target_peer_id": "peer2"
            }
            await mgr.forward_signal(room_id, "peer1", offer_payload)

            # Verify peer2 received the offer with sender_peer_id set
            assert ws2.send_json.call_args[0][0]["type"] == "offer"
            assert ws2.send_json.call_args[0][0]["sender_peer_id"] == "peer1"

            # Broadcast room chat from peer2
            chat_payload = {
                "type": "chat",
                "text": "Hello classmates!"
            }
            await mgr.forward_signal(room_id, "peer2", chat_payload)

            # Verify ws1 received the chat
            assert ws1.send_json.call_args[0][0]["type"] == "chat"
            assert ws1.send_json.call_args[0][0]["sender_peer_id"] == "peer2"

            # Disconnect
            await mgr.disconnect(room_id, "peer1")
            assert room_id in mgr.rooms
            assert "peer1" not in mgr.rooms[room_id]

            await mgr.disconnect(room_id, "peer2")
            assert room_id not in mgr.rooms

        asyncio.run(_run())
