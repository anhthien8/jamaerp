"""Pydantic schemas for auth & users."""

import json
from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime


# Vai trò hợp lệ — chặn gán role tùy ý (privilege escalation qua giá trị lạ)
VALID_ROLES = {
    "admin", "executive", "leader", "data_entry",
    "accountant", "supervisor",
}


class UserLogin(BaseModel):
    email: str
    password: str


class UserCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = "data_entry"
    department: str = "SALES"
    phone: str | None = Field(default=None, max_length=20)
    team_id: str | None = None


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    role: str | None = None
    department: str | None = None
    team_id: str | None = None
    is_active: bool | None = None
    telegram_user_id: int | None = None
    telegram_username: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    # Cấu hình lương (chỉ admin/kế toán) — thiếu 2 trường này nên payroll generate
    # toàn missing_grade → thực lĩnh 0đ, không có đường gán bậc lương (audit 22/07)
    salary_grade_id: str | None = None
    dependents_count: int | None = Field(default=None, ge=0, le=20)


class UserResponse(BaseModel):
    id: str
    full_name: str
    email: str
    phone: str | None = None
    role: str
    department: str
    team_id: str | None = None
    telegram_user_id: int | None = None
    telegram_username: str | None = None
    is_active: bool
    salary_grade_id: str | None = None
    dependents_count: int = 0
    resign_date: datetime | None = None
    resigned_by: str | None = None
    # Per-user permission overrides (JSON string stored in DB, parsed to dict for API)
    custom_permissions: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("custom_permissions", mode="before")
    @classmethod
    def _parse_custom_permissions(cls, v):
        """Parse JSON string from SQLAlchemy model to dict."""
        if v is None or isinstance(v, dict):
            return v
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return None


class CustomRoleCreate(BaseModel):
    role_key: str = Field(min_length=1, max_length=20)
    role_name: str = Field(min_length=1, max_length=50)
    department: str = Field(min_length=1, max_length=20)
    permissions: dict = Field(default_factory=dict)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TelegramAuth(BaseModel):
    telegram_user_id: int
    telegram_username: str | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str = Field(min_length=6, max_length=128)
