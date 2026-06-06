from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from fastapi import HTTPException, status
from app.models.course import Course, CourseSection, CourseContent, Enrollment, Category, CourseStatus
from app.models.user import User
from app.schemas.course import CourseCreateRequest, CourseUpdateRequest, SectionCreateRequest, ContentCreateRequest
import re
import uuid

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text

async def create_course(data: CourseCreateRequest, educator: User, db: AsyncSession):
    base_slug = slugify(data.title)
    slug = base_slug
    counter = 1
    while True:
        result = await db.execute(select(Course).where(Course.slug == slug))
        if not result.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    course = Course(
        educator_id=educator.id,
        title=data.title,
        slug=slug,
        description=data.description,
        category_id=uuid.UUID(data.category_id) if data.category_id else None,
        is_paid=data.is_paid,
        price=data.price if data.is_paid else 0.0
    )
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course

async def get_my_courses(educator: User, db: AsyncSession):
    result = await db.execute(
        select(Course).where(
            and_(Course.educator_id == educator.id, Course.is_deleted == False)
        ).order_by(Course.created_at.desc())
    )
    return result.scalars().all()

async def get_published_courses(db: AsyncSession, skip: int = 0, limit: int = 20):
    result = await db.execute(
        select(Course).where(
            and_(Course.status == CourseStatus.published, Course.is_deleted == False)
        ).offset(skip).limit(limit)
    )
    return result.scalars().all()

async def get_course_by_id(course_id: str, db: AsyncSession):
    result = await db.execute(
        select(Course).where(and_(Course.id == course_id, Course.is_deleted == False))
    )
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course

async def update_course(course_id: str, data: CourseUpdateRequest, educator: User, db: AsyncSession):
    course = await get_course_by_id(course_id, db)
    if str(course.educator_id) != str(educator.id):
        raise HTTPException(status_code=403, detail="Not your course")
    if data.title is not None:
        course.title = data.title
    if data.description is not None:
        course.description = data.description
    if data.is_paid is not None:
        course.is_paid = data.is_paid
    if data.price is not None:
        course.price = data.price
    await db.commit()
    await db.refresh(course)
    return course

async def publish_course(course_id: str, educator: User, db: AsyncSession):
    course = await get_course_by_id(course_id, db)
    if str(course.educator_id) != str(educator.id):
        raise HTTPException(status_code=403, detail="Not your course")
    course.status = CourseStatus.published
    await db.commit()
    await db.refresh(course)
    return course

async def delete_course(course_id: str, educator: User, db: AsyncSession):
    course = await get_course_by_id(course_id, db)
    if str(course.educator_id) != str(educator.id):
        raise HTTPException(status_code=403, detail="Not your course")
    course.is_deleted = True
    await db.commit()

async def create_section(course_id: str, data: SectionCreateRequest, educator: User, db: AsyncSession):
    course = await get_course_by_id(course_id, db)
    if str(course.educator_id) != str(educator.id):
        raise HTTPException(status_code=403, detail="Not your course")
    section = CourseSection(course_id=course.id, title=data.title, order_index=data.order_index)
    db.add(section)
    await db.commit()
    await db.refresh(section)
    return section

async def get_sections(course_id: str, db: AsyncSession):
    result = await db.execute(
        select(CourseSection).where(CourseSection.course_id == course_id).order_by(CourseSection.order_index)
    )
    return result.scalars().all()

async def create_content(course_id: str, section_id: str, data: ContentCreateRequest, educator: User, db: AsyncSession):
    course = await get_course_by_id(course_id, db)
    if str(course.educator_id) != str(educator.id):
        raise HTTPException(status_code=403, detail="Not your course")
    content = CourseContent(
        section_id=section_id,
        course_id=course_id,
        title=data.title,
        content_type=data.content_type.value,
        content_url=data.content_url,
        duration_seconds=data.duration_seconds,
        order_index=data.order_index,
        is_preview=data.is_preview
    )
    db.add(content)
    await db.commit()
    await db.refresh(content)
    return content

async def enroll_learner(course_id: str, learner: User, db: AsyncSession):
    course = await get_course_by_id(course_id, db)
    if course.status != CourseStatus.published:
        raise HTTPException(status_code=400, detail="Course is not published")
    existing = await db.execute(
        select(Enrollment).where(and_(Enrollment.learner_id == learner.id, Enrollment.course_id == course_id))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already enrolled")
    enrollment = Enrollment(learner_id=learner.id, course_id=course_id)
    db.add(enrollment)
    course.total_enrollments += 1
    await db.commit()
    await db.refresh(enrollment)
    return enrollment

async def get_enrolled_courses(learner: User, db: AsyncSession):
    result = await db.execute(
        select(Course).join(Enrollment, Enrollment.course_id == Course.id).where(
            and_(Enrollment.learner_id == learner.id, Course.is_deleted == False)
        )
    )
    return result.scalars().all()

async def get_categories(db: AsyncSession):
    result = await db.execute(select(Category).order_by(Category.name))
    return result.scalars().all()
