import uuid
from sqlalchemy import Column, String, Boolean, TIMESTAMP, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base

class LiveSession(Base):
    __tablename__ = "live_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    educator_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    room_id = Column(String(100), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    scheduled_at = Column(TIMESTAMP(timezone=True), nullable=True)
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    ended_at = Column(TIMESTAMP(timezone=True), nullable=True)
    is_active = Column(Boolean, default=False, nullable=False)
    recording_url = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
