import logging
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, get_redis
from app.dependencies import get_current_user, require_learner
from app.models.user import User
from app.schemas.proctor import (
    ProctorSessionResponse,
    FrameAnalyzeRequest,
    FrameAnalyzeResponse,
    TrustScoreResponse,
    EndProctorSessionResponse
)
from app.services.proctor_service import (
    init_proctor_session,
    get_trust_score,
    process_proctor_frame,
    end_proctor_session,
    manager,
    FLAG_THRESHOLD
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/sessions/{attempt_id}/start", response_model=ProctorSessionResponse, status_code=201)
async def start_session(
    attempt_id: str,
    current_user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    session = await init_proctor_session(attempt_id, db, redis)
    return ProctorSessionResponse(
        session_id=str(session.id),
        attempt_id=str(session.attempt_id),
        initial_trust_score=float(session.initial_trust_score),
        final_trust_score=float(session.final_trust_score) if session.final_trust_score is not None else None,
        is_flagged=session.is_flagged,
        total_alerts=session.total_alerts_count,
        started_at=session.started_at
    )

@router.post("/sessions/{attempt_id}/frame", response_model=FrameAnalyzeResponse)
async def analyze_frame(
    attempt_id: str,
    payload: FrameAnalyzeRequest,
    current_user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    result = await process_proctor_frame(
        attempt_id=attempt_id,
        frame_b64=payload.frame_base64,
        timestamp=payload.timestamp,
        db=db,
        redis_client=redis
    )
    return FrameAnalyzeResponse(**result)

@router.get("/sessions/{attempt_id}/trust-score", response_model=TrustScoreResponse)
async def read_trust_score(
    attempt_id: str,
    current_user: User = Depends(get_current_user),
    redis = Depends(get_redis)
):
    score = await get_trust_score(attempt_id, redis)
    return TrustScoreResponse(
        attempt_id=attempt_id,
        current_trust_score=score,
        is_flagged=score < FLAG_THRESHOLD,
        total_alerts=0
    )

@router.post("/sessions/{attempt_id}/end", response_model=EndProctorSessionResponse)
async def end_session(
    attempt_id: str,
    current_user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    session = await end_proctor_session(attempt_id, db, redis)
    return EndProctorSessionResponse(
        session_id=str(session.id),
        attempt_id=str(session.attempt_id),
        final_trust_score=float(session.final_trust_score) if session.final_trust_score is not None else 100.0,
        is_flagged=session.is_flagged,
        total_alerts=session.total_alerts_count,
        message="Proctor session finalized successfully"
    )

@router.websocket("/ws/{attempt_id}")
async def proctor_websocket(websocket: WebSocket, attempt_id: str):
    await manager.connect(attempt_id, websocket)
    try:
        while True:
            # Keep connection alive and listen for ping/heartbeat
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(attempt_id, websocket)
    except Exception as e:
        logger.error("WebSocket error for attempt %s: %s", attempt_id, e)
        manager.disconnect(attempt_id, websocket)
