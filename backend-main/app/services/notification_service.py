import uuid
import logging
from sqlalchemy import select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.notification import Notification, NotificationType

logger = logging.getLogger(__name__)

def _to_uuid(val):
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError):
        return val


async def create_notification(
    user_id: str,
    title: str,
    message: str,
    notification_type: str = "system",
    db: Optional[AsyncSession] = None
) -> Optional[Notification]:
    """
    Creates and commits a new notification for the specified user.
    """
    if db is None:
        return None

    try:
        # Map notification type
        n_type = NotificationType.system
        try:
            n_type = NotificationType(notification_type)
        except ValueError:
            n_type = NotificationType.system

        notif = Notification(
            user_id=_to_uuid(user_id),
            title=title,
            message=message,
            notification_type=n_type,
            is_read=False
        )
        db.add(notif)
        await db.commit()
        await db.refresh(notif)
        return notif
    except Exception as e:
        logger.error("Failed to create notification for user %s: %s", user_id, e)
        return None
