from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class UserStatusUpdateRequest(BaseModel):
    is_active: bool

class UserAdminResponse(BaseModel):
    id: str
    email: str
    role: str
    first_name: str
    last_name: str
    is_active: bool
    is_email_verified: bool
    created_at: datetime

class AdminUsersListResponse(BaseModel):
    users: List[UserAdminResponse]
    total: int
    page: int
    limit: int

class PlatformStatsResponse(BaseModel):
    total_users: int
    total_learners: int
    total_educators: int
    total_admins: int
    total_courses: int
    total_exams: int
    total_exam_attempts: int
    active_proctor_sessions: int
    flagged_proctor_sessions: int

class AuditLogResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    created_at: datetime
