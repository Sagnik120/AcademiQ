from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import (
    auth, users, courses, questions, exams,
    proctoring, genai, storage, admin, notifications, live_sessions
)

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5500", "http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(courses.router, prefix="/api/v1/courses", tags=["Courses"])
app.include_router(questions.router, prefix="/api/v1/educator/questions", tags=["Question Bank"])
app.include_router(exams.router, prefix="/api/v1", tags=["Exams"])
app.include_router(proctoring.router, prefix="/api/v1/proctor", tags=["Proctoring"])
app.include_router(genai.router, prefix="/api/v1/genai", tags=["AI Generation"])
app.include_router(storage.router, prefix="/api/v1/storage", tags=["Storage"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])
app.include_router(live_sessions.router, prefix="/api/v1/live", tags=["Live Sessions & WebRTC"])

@app.get("/")
async def root():
    return {"message": "PrepEz API is running", "docs": "/api/docs"}

@app.get("/health")
async def health():
    return {"status": "ok"}
