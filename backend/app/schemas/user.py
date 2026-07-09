"""Pydantic schemas for auth & users."""

from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


# Vai trò hợp lệ — chặn gán role tùy ý (privilege escalation qua giá trị lạ)
VALID_ROLES = {
    "admin", "executive", "leader", "data_entry",
    "accountant", "purchasing", "designer", "pm",
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
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TelegramAuth(BaseModel):
    telegram_user_id: int
    telegram_username: str | None = None
