from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.database import get_db
from app.dependencies import get_current_user, require_educator, require_learner
from app.models.user import User
from app.schemas.course import (
    CourseCreateRequest, CourseUpdateRequest, CourseResponse,
    SectionCreateRequest, SectionUpdateRequest, SectionResponse,
    ContentCreateRequest, ContentResponse,
    EnrollmentResponse, CategoryResponse, MessageResponse
)
from app.services.course_service import (
    create_course, get_my_courses, get_published_courses, get_course_by_id,
    update_course, publish_course, delete_course,
    create_section, get_sections,
    create_content, enroll_learner, get_enrolled_courses, get_categories
)

router = APIRouter()

# ── Public ────────────────────────────────────────
@router.get("/", response_model=List[CourseResponse])
async def list_courses(skip: int = Query(0), limit: int = Query(20), db: AsyncSession = Depends(get_db)):
    courses = await get_published_courses(db, skip, limit)
    return [CourseResponse(
        id=str(c.id), educator_id=str(c.educator_id), title=c.title, slug=c.slug,
        description=c.description, thumbnail_url=c.thumbnail_url, status=c.status.value,
        is_paid=c.is_paid, price=float(c.price), currency=c.currency,
        total_enrollments=c.total_enrollments, category_id=str(c.category_id) if c.category_id else None
    ) for c in courses]

@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories(db: AsyncSession = Depends(get_db)):
    cats = await get_categories(db)
    return [CategoryResponse(id=str(c.id), name=c.name, slug=c.slug, description=c.description) for c in cats]

@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(course_id: str, db: AsyncSession = Depends(get_db)):
    c = await get_course_by_id(course_id, db)
    return CourseResponse(
        id=str(c.id), educator_id=str(c.educator_id), title=c.title, slug=c.slug,
        description=c.description, thumbnail_url=c.thumbnail_url, status=c.status.value,
        is_paid=c.is_paid, price=float(c.price), currency=c.currency,
        total_enrollments=c.total_enrollments, category_id=str(c.category_id) if c.category_id else None
    )

# ── Learner ───────────────────────────────────────
@router.get("/learner/enrolled", response_model=List[CourseResponse])
async def my_enrolled_courses(current_user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)):
    courses = await get_enrolled_courses(current_user, db)
    return [CourseResponse(
        id=str(c.id), educator_id=str(c.educator_id), title=c.title, slug=c.slug,
        description=c.description, thumbnail_url=c.thumbnail_url, status=c.status.value,
        is_paid=c.is_paid, price=float(c.price), currency=c.currency,
        total_enrollments=c.total_enrollments, category_id=str(c.category_id) if c.category_id else None
    ) for c in courses]

@router.post("/{course_id}/enroll", response_model=EnrollmentResponse, status_code=201)
async def enroll(course_id: str, current_user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)):
    e = await enroll_learner(course_id, current_user, db)
    return EnrollmentResponse(id=str(e.id), learner_id=str(e.learner_id), course_id=str(e.course_id), status=e.status.value)

# ── Educator ──────────────────────────────────────
@router.get("/educator/my-courses", response_model=List[CourseResponse])
async def my_courses(current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    courses = await get_my_courses(current_user, db)
    return [CourseResponse(
        id=str(c.id), educator_id=str(c.educator_id), title=c.title, slug=c.slug,
        description=c.description, thumbnail_url=c.thumbnail_url, status=c.status.value,
        is_paid=c.is_paid, price=float(c.price), currency=c.currency,
        total_enrollments=c.total_enrollments, category_id=str(c.category_id) if c.category_id else None
    ) for c in courses]

@router.post("/educator/courses", response_model=CourseResponse, status_code=201)
async def create(data: CourseCreateRequest, current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    c = await create_course(data, current_user, db)
    return CourseResponse(
        id=str(c.id), educator_id=str(c.educator_id), title=c.title, slug=c.slug,
        description=c.description, thumbnail_url=c.thumbnail_url, status=c.status.value,
        is_paid=c.is_paid, price=float(c.price), currency=c.currency,
        total_enrollments=c.total_enrollments, category_id=str(c.category_id) if c.category_id else None
    )

@router.patch("/educator/courses/{course_id}", response_model=CourseResponse)
async def update(course_id: str, data: CourseUpdateRequest, current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    c = await update_course(course_id, data, current_user, db)
    return CourseResponse(
        id=str(c.id), educator_id=str(c.educator_id), title=c.title, slug=c.slug,
        description=c.description, thumbnail_url=c.thumbnail_url, status=c.status.value,
        is_paid=c.is_paid, price=float(c.price), currency=c.currency,
        total_enrollments=c.total_enrollments, category_id=str(c.category_id) if c.category_id else None
    )

@router.post("/educator/courses/{course_id}/publish", response_model=CourseResponse)
async def publish(course_id: str, current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    c = await publish_course(course_id, current_user, db)
    return CourseResponse(
        id=str(c.id), educator_id=str(c.educator_id), title=c.title, slug=c.slug,
        description=c.description, thumbnail_url=c.thumbnail_url, status=c.status.value,
        is_paid=c.is_paid, price=float(c.price), currency=c.currency,
        total_enrollments=c.total_enrollments, category_id=str(c.category_id) if c.category_id else None
    )

@router.delete("/educator/courses/{course_id}", response_model=MessageResponse)
async def delete(course_id: str, current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    await delete_course(course_id, current_user, db)
    return MessageResponse(message="Course deleted")

@router.post("/educator/courses/{course_id}/sections", response_model=SectionResponse, status_code=201)
async def add_section(course_id: str, data: SectionCreateRequest, current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    s = await create_section(course_id, data, current_user, db)
    return SectionResponse(id=str(s.id), course_id=str(s.course_id), title=s.title, order_index=s.order_index)

@router.get("/educator/courses/{course_id}/sections", response_model=List[SectionResponse])
async def list_sections(course_id: str, current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    sections = await get_sections(course_id, db)
    return [SectionResponse(id=str(s.id), course_id=str(s.course_id), title=s.title, order_index=s.order_index) for s in sections]

@router.post("/educator/courses/{course_id}/sections/{section_id}/content", response_model=ContentResponse, status_code=201)
async def add_content(course_id: str, section_id: str, data: ContentCreateRequest, current_user: User = Depends(require_educator), db: AsyncSession = Depends(get_db)):
    c = await create_content(course_id, section_id, data, current_user, db)
    return ContentResponse(
        id=str(c.id), section_id=str(c.section_id), course_id=str(c.course_id),
        title=c.title, content_type=c.content_type, content_url=c.content_url,
        duration_seconds=c.duration_seconds, order_index=c.order_index, is_preview=c.is_preview
    )
