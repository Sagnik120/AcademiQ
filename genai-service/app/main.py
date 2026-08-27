from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pathlib import Path
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Explicitly point to .env — works regardless of where uvicorn is launched from
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

_key = os.getenv("GEMINI_API_KEY")
logger.info("GEMINI_API_KEY loaded: %s", "YES ✓" if _key else f"NO — .env expected at: {env_path}")

from app.routers import grading, generation, pdf

app = FastAPI(
    title="PrepEz GenAI Service",
    description="LLM grading + question generation microservice",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(grading.router)
app.include_router(generation.router)
app.include_router(pdf.router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": "gemini-2.5-flash",
        "service": "genai-service",
        "api_key_loaded": bool(os.getenv("GEMINI_API_KEY")),
    }