import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_, desc, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.notification import Notification
from app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    MarkReadResponse
)

router = APIRouter()

def _to_uuid(val):
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError):
        return val


@router.get("", response_model=NotificationListResponse)
async def get_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetches user notifications with optional unread-only filtering."""
    filters = [Notification.user_id == current_user.id]
    if unread_only:
        filters.append(Notification.is_read == False)

    query = select(Notification).where(and_(*filters)).order_by(desc(Notification.created_at)).limit(limit)
    result = await db.execute(query)
    notifications = result.scalars().all()

    # Unread count
    unread_res = await db.execute(
        select(func.count(Notification.id)).where(
            and_(Notification.user_id == current_user.id, Notification.is_read == False)
        )
    )
    unread_count = unread_res.scalar() or 0

    return NotificationListResponse(
        notifications=[
            NotificationResponse(
                id=str(n.id),
                user_id=str(n.user_id),
                title=n.title,
                message=n.message,
                notification_type=n.notification_type.value if hasattr(n.notification_type, "value") else str(n.notification_type),
                is_read=n.is_read,
                created_at=n.created_at
            )
            for n in notifications
        ],
        unread_count=unread_count
    )


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Marks a single notification as read."""
    notif_uuid = _to_uuid(notification_id)
    result = await db.execute(
        select(Notification).where(
            and_(Notification.id == notif_uuid, Notification.user_id == current_user.id)
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.is_read = True
    await db.commit()
    await db.refresh(notif)

    return NotificationResponse(
        id=str(notif.id),
        user_id=str(notif.user_id),
        title=notif.title,
        message=notif.message,
        notification_type=notif.notification_type.value if hasattr(notif.notification_type, "value") else str(notif.notification_type),
        is_read=notif.is_read,
        created_at=notif.created_at
    )


@router.post("/read-all", response_model=MarkReadResponse)
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Marks all unread notifications for the user as read."""
    result = await db.execute(
        select(Notification).where(
            and_(Notification.user_id == current_user.id, Notification.is_read == False)
        )
    )
    unread_notifs = result.scalars().all()
    count = len(unread_notifs)

    for n in unread_notifs:
        n.is_read = True

    await db.commit()

    return MarkReadResponse(
        message="All notifications marked as read",
        marked_count=count
    )
