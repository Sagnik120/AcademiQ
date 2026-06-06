from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "PrepEz"
    APP_ENV: str = "development"
    SECRET_KEY: str = "prepez_super_secret_key_change_this_in_production_32chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    DATABASE_URL: str = "postgresql+asyncpg://prepez_user:your_password@localhost:5432/prepez_db"
    REDIS_URL: str = "redis://localhost:6379"

    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    RESEND_API_KEY: str = ""

    ML_SERVICE_URL: str = "http://localhost:8001"
    GENAI_SERVICE_URL: str = "http://localhost:8002"

    FRONTEND_URL: str = "http://127.0.0.1:5500"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
