from pydantic import BaseModel, field_validator
from typing import Optional, List
from enum import Enum
import re

class CourseStatusEnum(str, Enum):
    draft = "draft"
    published = "published"
    archived = "archived"

class ContentTypeEnum(str, Enum):
    video = "video"
    document = "document"
    link = "link"

# ── Category ──────────────────────────────────────
class CategoryResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    class Config:
        from_attributes = True

# ── Course ────────────────────────────────────────
class CourseCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    category_id: Optional[str] = None
    is_paid: bool = False
    price: float = 0.0

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()

class CourseUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[str] = None
    is_paid: Optional[bool] = None
    price: Optional[float] = None

class CourseResponse(BaseModel):
    id: str
    educator_id: str
    title: str
    slug: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    status: str
    is_paid: bool
    price: float
    currency: str
    total_enrollments: int
    category_id: Optional[str] = None
    class Config:
        from_attributes = True

# ── Section ───────────────────────────────────────
class SectionCreateRequest(BaseModel):
    title: str
    order_index: int

class SectionUpdateRequest(BaseModel):
    title: Optional[str] = None
    order_index: Optional[int] = None

class SectionResponse(BaseModel):
    id: str
    course_id: str
    title: str
    order_index: int
    class Config:
        from_attributes = True

# ── Content ───────────────────────────────────────
class ContentCreateRequest(BaseModel):
    title: str
    content_type: ContentTypeEnum
    content_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    order_index: int
    is_preview: bool = False

class ContentResponse(BaseModel):
    id: str
    section_id: str
    course_id: str
    title: str
    content_type: str
    content_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    order_index: int
    is_preview: bool
    class Config:
        from_attributes = True

# ── Enrollment ────────────────────────────────────
class EnrollmentResponse(BaseModel):
    id: str
    learner_id: str
    course_id: str
    status: str
    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    message: str
