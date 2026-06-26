"""Pydantic schemas for auth & users."""

from pydantic import BaseModel, EmailStr
from datetime import datetime


class UserLogin(BaseModel):
    email: str
    password: str


class UserCreate(BaseModel):
    full_name: str
    email: str
    password: str
    role: str = "data_entry"
    department: str = "SALES"
    phone: str | None = None
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
