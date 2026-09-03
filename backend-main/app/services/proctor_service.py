import uuid
import logging
import time
import httpx
from typing import Optional, Dict, List
from fastapi import WebSocket, HTTPException
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.exam import ExamAttempt
from app.models.proctor import ProctorSession, ProctorAlert, AlertType, AlertSeverity

logger = logging.getLogger(__name__)

TRUST_DEDUCTIONS = {
    "head_turn_severe": 5.00,
    "head_turn_mild": 2.00,
    "head_down": 2.00,
    "absent": 8.00,
    "absent_extended": 15.00,
    "multiple_face": 10.00,
    "tab_switch": 5.00,
}

FLAG_THRESHOLD = 60.00

# In-memory fallback if Redis is unavailable or during tests
_in_memory_trust: Dict[str, float] = {}

def _to_uuid(val):
    """Converts a string or UUID to a uuid.UUID object for SQLite/Postgres compatibility."""
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError):
        return val

class ConnectionManager:
    """Manages real-time WebSocket connections per attempt_id."""
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, attempt_id: str, websocket: WebSocket):
        await websocket.accept()
        if attempt_id not in self.active_connections:
            self.active_connections[attempt_id] = []
        self.active_connections[attempt_id].append(websocket)

    def disconnect(self, attempt_id: str, websocket: WebSocket):
        if attempt_id in self.active_connections:
            if websocket in self.active_connections[attempt_id]:
                self.active_connections[attempt_id].remove(websocket)
            if not self.active_connections[attempt_id]:
                del self.active_connections[attempt_id]

    async def broadcast(self, attempt_id: str, message: dict):
        if attempt_id in self.active_connections:
            for connection in list(self.active_connections[attempt_id]):
                try:
                    await connection.send_json(message)
                except Exception:
                    self.disconnect(attempt_id, connection)

manager = ConnectionManager()


async def init_proctor_session(attempt_id: str, db: AsyncSession, redis_client=None) -> ProctorSession:
    """Initializes proctor session in DB and seeds initial trust score of 100 in Redis."""
    att_uuid = _to_uuid(attempt_id)
    attempt_res = await db.execute(select(ExamAttempt).where(ExamAttempt.id == att_uuid))
    attempt = attempt_res.scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Exam attempt not found")

    # Check if session already exists
    sess_res = await db.execute(select(ProctorSession).where(ProctorSession.attempt_id == att_uuid))
    session = sess_res.scalar_one_or_none()
    if not session:
        session = ProctorSession(
            attempt_id=att_uuid,
            initial_trust_score=100.00,
            is_flagged=False
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

    # Set initial score in Redis
    key = f"proctor:trust:{attempt_id}"
    if redis_client:
        try:
            await redis_client.set(key, 100.00, ex=86400) # 24 hr TTL
        except Exception as e:
            logger.warning("Redis set failed for %s, falling back to memory: %s", key, e)
            _in_memory_trust[attempt_id] = 100.00
    else:
        _in_memory_trust[attempt_id] = 100.00

    return session


async def get_trust_score(attempt_id: str, redis_client=None) -> float:
    """Fetches the current live trust score from Redis or memory fallback."""
    key = f"proctor:trust:{attempt_id}"
    if redis_client:
        try:
            score = await redis_client.get(key)
            if score is not None:
                return float(score)
        except Exception as e:
            logger.warning("Redis get failed for %s: %s", key, e)
    return float(_in_memory_trust.get(attempt_id, 100.00))


async def process_proctor_frame(
    attempt_id: str,
    frame_b64: str,
    timestamp: Optional[float],
    db: AsyncSession,
    redis_client=None
) -> dict:
    """
    Sends frame to ML service, records alerts, updates Redis trust scores,
    auto-flags if score drops below threshold, and broadcasts over WebSocket.
    """
    ts = timestamp if timestamp and timestamp > 0 else time.time()
    att_uuid = _to_uuid(attempt_id)
    
    # 1. Forward frame to ML service
    url = f"{settings.ML_SERVICE_URL.rstrip('/')}/analyze-frame"
    payload = {
        "frame_base64": frame_b64,
        "attempt_id": str(attempt_id),
        "timestamp": ts
    }

    alert_type = None
    severity = None
    confidence = 1.0

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                alert_type = data.get("alert_type")
                severity = data.get("severity")
                confidence = data.get("confidence", 1.0)
            else:
                logger.error("ML service returned status %d: %s", resp.status_code, resp.text)
    except Exception as e:
        logger.error("ML service connection failed at %s: %s", url, e)

    # 2. Get current score and apply deduction if alert triggered
    current_score = await get_trust_score(attempt_id, redis_client)
    deduction = 0.0

    # Fetch proctor session
    sess_res = await db.execute(select(ProctorSession).where(ProctorSession.attempt_id == att_uuid))
    session = sess_res.scalar_one_or_none()

    if alert_type and alert_type in TRUST_DEDUCTIONS:
        deduction = TRUST_DEDUCTIONS[alert_type]
        new_score = max(0.00, round(current_score - deduction, 2))
        
        # Update Redis / Memory
        key = f"proctor:trust:{attempt_id}"
        if redis_client:
            try:
                await redis_client.set(key, new_score, ex=86400)
            except Exception:
                _in_memory_trust[attempt_id] = new_score
        else:
            _in_memory_trust[attempt_id] = new_score

        current_score = new_score

        # Log alert to DB
        alert_record = ProctorAlert(
            session_id=session.id if session else None,
            attempt_id=att_uuid,
            alert_type=alert_type,
            severity=severity or "medium",
            confidence=confidence,
            trust_deduction=deduction,
            timestamp=ts
        )
        db.add(alert_record)

        if session:
            session.total_alerts_count += 1
            if current_score < FLAG_THRESHOLD:
                session.is_flagged = True

        await db.commit()

        # 3. Broadcast real-time update to active WebSocket listeners
        await manager.broadcast(attempt_id, {
            "type": "proctor_alert",
            "alert_type": alert_type,
            "severity": severity,
            "trust_score": current_score,
            "is_flagged": session.is_flagged if session else (current_score < FLAG_THRESHOLD),
            "timestamp": ts
        })
    
    is_flagged = session.is_flagged if session else (current_score < FLAG_THRESHOLD)

    return {
        "alert_type": alert_type,
        "severity": severity,
        "confidence": confidence,
        "current_trust_score": current_score,
        "is_flagged": is_flagged
    }


async def end_proctor_session(attempt_id: str, db: AsyncSession, redis_client=None) -> ProctorSession:
    """Finalizes session, updates final trust score on ExamAttempt and ProctorSession."""
    att_uuid = _to_uuid(attempt_id)
    sess_res = await db.execute(select(ProctorSession).where(ProctorSession.attempt_id == att_uuid))
    session = sess_res.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Proctor session not found")

    final_score = await get_trust_score(attempt_id, redis_client)

    session.final_trust_score = final_score
    session.ended_at = func.now()

    # Sync back to ExamAttempt
    att_res = await db.execute(select(ExamAttempt).where(ExamAttempt.id == att_uuid))
    attempt = att_res.scalar_one_or_none()
    if attempt:
        attempt.final_trust_score = final_score
        if session.is_flagged:
            attempt.is_flagged = True

    await db.commit()
    await db.refresh(session)
    return session
