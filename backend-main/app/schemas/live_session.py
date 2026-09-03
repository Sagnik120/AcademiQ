from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class CreateLiveSessionRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    course_id: Optional[str] = None
    scheduled_at: Optional[datetime] = None

class LiveSessionResponse(BaseModel):
    id: str
    course_id: Optional[str] = None
    host_educator_id: str
    title: str
    room_id: str
    scheduled_at: Optional[datetime] = None
    is_active: bool
    ended_at: Optional[datetime] = None
    created_at: datetime
