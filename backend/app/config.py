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
    # In mọi câu SQL ra log — chỉ bật khi gỡ lỗi. Bật mặc định từng làm prod
    # vượt giới hạn 500 dòng log/giây của Railway và chậm mọi request (24/10).
    SQL_ECHO: bool = False
    LOG_LEVEL: str = "INFO"
    TIMEZONE: str = "Asia/Ho_Chi_Minh"

    # Worker nhúng: chạy job nền (backup + tự động hóa) NGAY trong tiến trình
    # uvicorn qua lifespan. Railway prod chỉ chạy uvicorn (start.sh) — không có
    # tiến trình worker riêng — nên PHẢI bật để job định kỳ sống trên prod.
    # Compose/VPS đã có service `worker` riêng → đặt EMBED_WORKER=false để
    # chống chạy đôi (double-run).
    EMBED_WORKER: bool = True

    # Database — SQLite by default for easy local dev
    # Production: set DATABASE_URL to Postgres (Railway cấp dạng postgres://,
    # được chuẩn hóa sang postgresql+asyncpg:// bên dưới)
    DATABASE_URL: str = "sqlite+aiosqlite:///./jama.db"

    # Redis (optional)
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    # 12 tiếng — phủ trọn một ngày làm việc (7h sáng đến 19h tối).
    # Để 8 tiếng thì người đăng nhập lúc 8h sáng bị hết phiên ngay giữa buổi chiều.
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 720

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_WEBHOOK_URL: str = ""
    # Bí mật chia sẻ giữa bot ↔ backend cho /auth/telegram.
    # Khi được đặt, backend BẮT BUỘC bot gửi header X-Telegram-Bot-Secret khớp,
    # ngăn kẻ tấn công mạo danh nhân viên chỉ bằng telegram_user_id.
    TELEGRAM_AUTH_SECRET: str = ""

    # Web Push (25/10/2026) — khoá VAPID sinh một lần, đặt env trên Railway.
    # Thiếu khoá → nút «Bật thông báo trên máy này» báo chưa cấu hình.
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = "https://crm.jamahome.vn"

    # Kho ảnh công trình (Đợt 2, 23/10/2026): bản sao ảnh sang Google Drive công
    # ty bằng Service Account. GDRIVE_SA_JSON = nguyên nội dung file key JSON;
    # GDRIVE_MEDIA_FOLDER_ID = thư mục gốc đã share quyền Editor cho email SA.
    # Thiếu một trong hai → bỏ qua bước sao (ảnh vẫn nằm ở nhóm Telegram).
    GDRIVE_SA_JSON: str = ""
    GDRIVE_MEDIA_FOLDER_ID: str = ""

    # Zalo Listener (spec 09): bí mật chia sẻ giữa Ingest Service (zca-js) ↔ backend.
    # Ingest service BẮT BUỘC gửi header X-Zalo-Secret khớp khi đẩy QR/heartbeat/tin nhắn.
    ZALO_INGEST_SECRET: str = ""

    # API
    API_BASE_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"
    # Dev: liệt kê vài cổng localhost thường gặp (Next tự nhảy cổng khi 3000 bận).
    # Production đặt qua biến môi trường CORS_ORIGINS (ghi đè mặc định này).
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:3003,http://localhost:8000"

    # Sentry (optional — bật khi đặt DSN; cần pip install sentry-sdk)
    SENTRY_DSN: str = ""

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
