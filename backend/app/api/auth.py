"""Auth API — login, telegram auth, seed admin."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, Team
from app.schemas.user import (
    UserLogin, TokenResponse, UserResponse, UserCreate, TelegramAuth,
)
from app.middleware.auth import (
    verify_password, hash_password, create_access_token, get_current_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Email + password login → JWT."""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị vô hiệu hóa")

    token = create_access_token(str(user.id), user.role, user.department)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/telegram", response_model=TokenResponse)
async def telegram_auth(data: TelegramAuth, db: AsyncSession = Depends(get_db)):
    """Telegram user_id → JWT. Used by bot to authenticate users."""
    result = await db.execute(
        select(User).where(User.telegram_user_id == data.telegram_user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Telegram chưa được liên kết với tài khoản CRM. Liên hệ Admin.",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị vô hiệu hóa")

    # Update TG username if changed
    if data.telegram_username and user.telegram_username != data.telegram_username:
        user.telegram_username = data.telegram_username
        await db.flush()

    token = create_access_token(str(user.id), user.role, user.department)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return UserResponse.model_validate(current_user)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all users (for assignment dropdowns etc)."""
    result = await db.execute(select(User).where(User.is_active == True).order_by(User.full_name))
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]
