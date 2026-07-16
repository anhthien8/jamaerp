"""JAMA HOME CRM Backend Configuration."""

from pydantic import field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # App
    APP_NAME: str = "JAMA HOME CRM"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    TIMEZONE: str = "Asia/Ho_Chi_Minh"

    # Database — SQLite by default for easy local dev
    # Production: set DATABASE_URL to Postgres (Railway cấp dạng postgres://,
    # được chuẩn hóa sang postgresql+asyncpg:// bên dưới)
    DATABASE_URL: str = "sqlite+aiosqlite:///./jama.db"

    # Redis (optional)
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_WEBHOOK_URL: str = ""
    # Bí mật chia sẻ giữa bot ↔ backend cho /auth/telegram.
    # Khi được đặt, backend BẮT BUỘC bot gửi header X-Telegram-Bot-Secret khớp,
    # ngăn kẻ tấn công mạo danh nhân viên chỉ bằng telegram_user_id.
    TELEGRAM_AUTH_SECRET: str = ""

    # Zalo Listener (spec 09): bí mật chia sẻ giữa Ingest Service (zca-js) ↔ backend.
    # Ingest service BẮT BUỘC gửi header X-Zalo-Secret khớp khi đẩy QR/heartbeat/tin nhắn.
    ZALO_INGEST_SECRET: str = ""

    # API
    API_BASE_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001,http://localhost:8000"

    # LLM (optional — rule-based fallback if empty)
    LLM_PROVIDER: str = "groq"
    LLM_MODEL: str = "groq/llama-3.3-70b-versatile"
    LLM_API_KEY: str = ""
    LLM_FALLBACK_MODEL: str = "ollama/llama3.2"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        """Railway/Heroku cấp postgres:// — SQLAlchemy async cần postgresql+asyncpg://."""
        if not isinstance(v, str) or not v:
            return v
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.DATABASE_URL

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
