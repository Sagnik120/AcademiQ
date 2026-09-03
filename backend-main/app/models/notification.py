import uuid
import enum
from sqlalchemy import Column, String, Boolean, Enum as PgEnum, TIMESTAMP, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base

class NotificationType(str, enum.Enum):
    exam_graded = "exam_graded"
    exam_scheduled = "exam_scheduled"
    attempt_flagged = "attempt_flagged"
    course_announcement = "course_announcement"
    system = "system"

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(PgEnum(NotificationType, name="notification_type", create_type=False), nullable=False, default=NotificationType.system)
    is_read = Column(Boolean, default=False, nullable=False)
    action_url = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
