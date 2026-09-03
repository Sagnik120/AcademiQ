import uuid
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin
from app.models.user import User, UserRole
from app.models.course import Course
from app.models.exam import Exam, ExamAttempt
from app.models.proctor import ProctorSession
from app.models.audit import AuditLog
from app.schemas.admin import (
    UserStatusUpdateRequest,
    UserAdminResponse,
    AdminUsersListResponse,
    PlatformStatsResponse,
    AuditLogResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)

def _to_uuid(val):
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError):
        return val


@router.get("/users", response_model=AdminUsersListResponse)
async def list_users(
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Admin-only: Paginated and filterable user directory."""
    query = select(User)
    count_query = select(func.count(User.id))

    filters = []
    if role:
        filters.append(User.role == role)
    if is_active is not None:
        filters.append(User.is_active == is_active)

    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))

    # Total count
    total_res = await db.execute(count_query)
    total_count = total_res.scalar() or 0

    # Paginated results
    offset = (page - 1) * limit
    result = await db.execute(query.order_by(desc(User.created_at)).offset(offset).limit(limit))
    users = result.scalars().all()

    return AdminUsersListResponse(
        users=[
            UserAdminResponse(
                id=str(u.id),
                email=u.email,
                role=u.role.value if hasattr(u.role, "value") else str(u.role),
                first_name=u.first_name,
                last_name=u.last_name,
                is_active=u.is_active,
                is_email_verified=u.is_email_verified,
                created_at=u.created_at
            )
            for u in users
        ],
        total=total_count,
        page=page,
        limit=limit
    )


@router.patch("/users/{user_id}/status", response_model=UserAdminResponse)
async def update_user_status(
    user_id: str,
    payload: UserStatusUpdateRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Admin-only: Activate, deactivate, or ban a user, logging the change to audit logs."""
    target_uuid = _to_uuid(user_id)
    result = await db.execute(select(User).where(User.id == target_uuid))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    old_status = target_user.is_active
    target_user.is_active = payload.is_active

    # Record audit log
    client_ip = request.client.host if request.client else None
    audit_entry = AuditLog(
        user_id=current_user.id,
        action="update_user_status",
        resource_type="user",
        resource_id=str(target_user.id),
        ip_address=client_ip,
        details={
            "target_user_email": target_user.email,
            "old_active_status": old_status,
            "new_active_status": payload.is_active
        }
    )
    db.add(audit_entry)
    await db.commit()
    await db.refresh(target_user)

    return UserAdminResponse(
        id=str(target_user.id),
        email=target_user.email,
        role=target_user.role.value if hasattr(target_user.role, "value") else str(target_user.role),
        first_name=target_user.first_name,
        last_name=target_user.last_name,
        is_active=target_user.is_active,
        is_email_verified=target_user.is_email_verified,
        created_at=target_user.created_at
    )


@router.get("/stats", response_model=PlatformStatsResponse)
async def get_platform_stats(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Admin-only: Aggregate system statistics for dashboard visualization."""
    # 1. Total users
    u_total = (await db.execute(select(func.count(User.id)))).scalar() or 0
    u_learners = (await db.execute(select(func.count(User.id)).where(User.role == UserRole.learner))).scalar() or 0
    u_educators = (await db.execute(select(func.count(User.id)).where(User.role == UserRole.educator))).scalar() or 0
    u_admins = (await db.execute(select(func.count(User.id)).where(User.role == UserRole.admin))).scalar() or 0

    # 2. Courses, Exams, Attempts
    c_total = (await db.execute(select(func.count(Course.id)))).scalar() or 0
    e_total = (await db.execute(select(func.count(Exam.id)))).scalar() or 0
    att_total = (await db.execute(select(func.count(ExamAttempt.id)))).scalar() or 0

    # 3. Proctoring stats
    proc_active = (await db.execute(select(func.count(ProctorSession.id)).where(ProctorSession.ended_at == None))).scalar() or 0
    proc_flagged = (await db.execute(select(func.count(ProctorSession.id)).where(ProctorSession.is_flagged == True))).scalar() or 0

    return PlatformStatsResponse(
        total_users=u_total,
        total_learners=u_learners,
        total_educators=u_educators,
        total_admins=u_admins,
        total_courses=c_total,
        total_exams=e_total,
        total_exam_attempts=att_total,
        active_proctor_sessions=proc_active,
        flagged_proctor_sessions=proc_flagged
    )


@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def list_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Admin-only: Retrieve recent security and administrative audit logs."""
    result = await db.execute(select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit))
    logs = result.scalars().all()

    return [
        AuditLogResponse(
            id=str(log.id),
            user_id=str(log.user_id) if log.user_id else None,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=str(log.resource_id) if log.resource_id else None,
            ip_address=log.ip_address,
            details=log.details if isinstance(log.details, dict) else None,
            created_at=log.created_at
        )
        for log in logs
    ]
