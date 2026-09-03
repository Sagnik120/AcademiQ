import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_educator
from app.models.user import User
from app.models.live_session import LiveSession
from app.schemas.live_session import (
    CreateLiveSessionRequest,
    LiveSessionResponse
)
from app.services.live_session_service import signaling_manager

router = APIRouter()
logger = logging.getLogger(__name__)

def _to_uuid(val):
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError):
        return val


@router.post("/sessions", response_model=LiveSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_live_session(
    payload: CreateLiveSessionRequest,
    current_user: User = Depends(require_educator),
    db: AsyncSession = Depends(get_db)
):
    """Educator-only: Schedules or immediately launches a WebRTC live classroom."""
    course_uuid = _to_uuid(payload.course_id) if payload.course_id else None
    unique_room = f"room_{uuid.uuid4().hex[:12]}"

    session = LiveSession(
        course_id=course_uuid,
        host_educator_id=current_user.id,
        title=payload.title,
        room_id=unique_room,
        scheduled_at=payload.scheduled_at,
        is_active=True
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return LiveSessionResponse(
        id=str(session.id),
        course_id=str(session.course_id) if session.course_id else None,
        host_educator_id=str(session.host_educator_id),
        title=session.title,
        room_id=session.room_id,
        scheduled_at=session.scheduled_at,
        is_active=session.is_active,
        ended_at=session.ended_at,
        created_at=session.created_at
    )


@router.get("/sessions", response_model=List[LiveSessionResponse])
async def list_live_sessions(
    course_id: Optional[str] = Query(None),
    active_only: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lists scheduled and active live classroom sessions."""
    filters = []
    if course_id:
        filters.append(LiveSession.course_id == _to_uuid(course_id))
    if active_only:
        filters.append(LiveSession.is_active == True)

    query = select(LiveSession)
    if filters:
        query = query.where(and_(*filters))
    query = query.order_by(desc(LiveSession.created_at)).limit(50)

    result = await db.execute(query)
    sessions = result.scalars().all()

    return [
        LiveSessionResponse(
            id=str(s.id),
            course_id=str(s.course_id) if s.course_id else None,
            host_educator_id=str(s.host_educator_id),
            title=s.title,
            room_id=s.room_id,
            scheduled_at=s.scheduled_at,
            is_active=s.is_active,
            ended_at=s.ended_at,
            created_at=s.created_at
        )
        for s in sessions
    ]


@router.get("/sessions/{room_id}", response_model=LiveSessionResponse)
async def get_live_session(
    room_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves metadata and status for a specific WebRTC room."""
    result = await db.execute(select(LiveSession).where(LiveSession.room_id == room_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Live classroom session not found")

    return LiveSessionResponse(
        id=str(session.id),
        course_id=str(session.course_id) if session.course_id else None,
        host_educator_id=str(session.host_educator_id),
        title=session.title,
        room_id=session.room_id,
        scheduled_at=session.scheduled_at,
        is_active=session.is_active,
        ended_at=session.ended_at,
        created_at=session.created_at
    )


@router.patch("/sessions/{room_id}/end", response_model=LiveSessionResponse)
async def end_live_session(
    room_id: str,
    current_user: User = Depends(require_educator),
    db: AsyncSession = Depends(get_db)
):
    """Educator-only: Concludes the live classroom session."""
    result = await db.execute(select(LiveSession).where(LiveSession.room_id == room_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Live classroom session not found")

    if session.host_educator_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to end this session")

    session.is_active = False
    session.ended_at = func.now()
    await db.commit()
    await db.refresh(session)

    return LiveSessionResponse(
        id=str(session.id),
        course_id=str(session.course_id) if session.course_id else None,
        host_educator_id=str(session.host_educator_id),
        title=session.title,
        room_id=session.room_id,
        scheduled_at=session.scheduled_at,
        is_active=session.is_active,
        ended_at=session.ended_at,
        created_at=session.created_at
    )


@router.websocket("/ws/{room_id}")
async def live_signaling_websocket(
    websocket: WebSocket,
    room_id: str,
    peer_id: Optional[str] = Query(None)
):
    """
    Real-time WebRTC signaling WebSocket endpoint.
    Transfers SDP offers, answers, ICE candidates, and text chat messages between peers.
    """
    pid = peer_id or f"peer_{uuid.uuid4().hex[:8]}"
    await signaling_manager.connect(room_id, pid, websocket)

    try:
        while True:
            data = await websocket.receive_json()
            # Forward signaling payload
            await signaling_manager.forward_signal(room_id, pid, data)
    except WebSocketDisconnect:
        await signaling_manager.disconnect(room_id, pid)
    except Exception as e:
        logger.error("WebRTC signaling error for peer %s in room %s: %s", pid, room_id, e)
        await signaling_manager.disconnect(room_id, pid)
