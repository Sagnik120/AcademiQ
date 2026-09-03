import uuid
import enum
from sqlalchemy import Column, String, Boolean, Enum as PgEnum, TIMESTAMP, Text, Integer, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base

class AlertSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

class AlertType(str, enum.Enum):
    head_turn_mild = "head_turn_mild"
    head_turn_severe = "head_turn_severe"
    head_down = "head_down"
    absent = "absent"
    absent_extended = "absent_extended"
    multiple_face = "multiple_face"
    tab_switch = "tab_switch"

class ProctorSession(Base):
    __tablename__ = "proctor_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id = Column(UUID(as_uuid=True), ForeignKey("exam_attempts.id", ondelete="CASCADE"), unique=True, nullable=False)
    started_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    ended_at = Column(TIMESTAMP(timezone=True), nullable=True)
    initial_trust_score = Column(Numeric(5, 2), default=100.00, nullable=False)
    final_trust_score = Column(Numeric(5, 2), nullable=True)
    is_flagged = Column(Boolean, default=False, nullable=False)
    total_alerts_count = Column(Integer, default=0, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

class ProctorAlert(Base):
    __tablename__ = "proctor_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("proctor_sessions.id", ondelete="CASCADE"), nullable=True)
    attempt_id = Column(UUID(as_uuid=True), ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=False)
    alert_type = Column(PgEnum(AlertType, name="alert_type", create_type=False), nullable=False)
    severity = Column(PgEnum(AlertSeverity, name="alert_severity", create_type=False), nullable=False)
    confidence = Column(Numeric(4, 3), nullable=True, default=1.0)
    trust_deduction = Column(Numeric(5, 2), default=0.00, nullable=False)
    snapshot_url = Column(Text, nullable=True)
    timestamp = Column(Numeric(16, 4), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
