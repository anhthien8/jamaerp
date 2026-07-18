"""Auth API — login, telegram auth, seed admin."""

import hmac
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import User, Team
from app.schemas.user import (
    UserLogin, TokenResponse, UserResponse, UserCreate, TelegramAuth,
    ChangePasswordRequest, ForgotPasswordRequest, ResetPasswordRequest,
)
from app.middleware.auth import (
    verify_password, hash_password, create_access_token, get_current_user,
)

settings = get_settings()

# ── In-memory rate limiter (login + telegram auth) ────────────────────────
# key = bucket string, value = list of attempt timestamps (epoch seconds)
_login_attempts: dict[str, list[float]] = defaultdict(list)
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 60


def _check_rate_limit(bucket: str, max_attempts: int = _LOGIN_MAX_ATTEMPTS) -> None:
    """Raise 429 if *bucket* has exceeded the allowed attempts in the window."""
    now = time.time()
    _login_attempts[bucket] = [
        ts for ts in _login_attempts[bucket] if now - ts < _LOGIN_WINDOW_SECONDS
    ]
    if not _login_attempts[bucket]:
        del _login_attempts[bucket]
    elif len(_login_attempts[bucket]) >= max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Quá nhiều yêu cầu. Vui lòng thử lại sau.",
        )
    _login_attempts[bucket].append(now)


# Backward-compat alias
def _check_login_rate_limit(ip: str) -> None:
    _check_rate_limit(f"login:{ip}")

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Quên mật khẩu: mã 6 số gửi qua Telegram, lưu in-memory (single instance) ──
# key = email thường hoá, value = (code, expires_epoch, attempts_left)
_reset_codes: dict[str, tuple[str, float, int]] = {}
_RESET_TTL_SECONDS = 15 * 60
_RESET_MAX_ATTEMPTS = 5


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Người dùng tự đổi mật khẩu (cần mật khẩu cũ)."""
    if not verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng")
    current_user.password_hash = hash_password(data.new_password)
    await db.flush()
    return {"status": "ok", "message": "Đã đổi mật khẩu"}


@router.post("/forgot-password")
async def forgot_password(request: Request, data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Gửi mã đặt lại mật khẩu qua Telegram đã liên kết.

    Luôn trả thông điệp chung (không lộ email nào tồn tại). Chỉ gửi được khi
    user đã liên kết telegram_user_id — không cần email server.
    """
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(f"forgot:{client_ip}", max_attempts=5)

    email = data.email.strip().lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None and "@" not in email and email:
        safe = email.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        result = await db.execute(select(User).where(User.email.ilike(f"{safe}@%", escape="\\")))
        matches = result.scalars().all()
        user = matches[0] if len(matches) == 1 else None

    generic = {
        "status": "ok",
        "message": "Nếu tài khoản tồn tại và đã liên kết Telegram, mã đặt lại đã được gửi qua bot (hiệu lực 15 phút).",
    }
    if not user or not user.is_active or not user.telegram_user_id:
        return generic

    import secrets as _secrets
    code = f"{_secrets.randbelow(1_000_000):06d}"
    _reset_codes[user.email.lower()] = (code, time.time() + _RESET_TTL_SECONDS, _RESET_MAX_ATTEMPTS)

    from app.services.telegram_notify import send_telegram
    await send_telegram(
        user.telegram_user_id,
        f"🔐 Mã đặt lại mật khẩu JAMA ERP của bạn: <b>{code}</b>\n"
        f"Hiệu lực 15 phút. Nếu không phải bạn yêu cầu, hãy bỏ qua tin này.",
    )
    return generic


@router.post("/reset-password")
async def reset_password(request: Request, data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Đặt mật khẩu mới bằng mã đã gửi qua Telegram."""
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(f"reset:{client_ip}", max_attempts=10)

    email = data.email.strip().lower()
    if "@" not in email:
        # cho phép tên ngắn giống login: tra email đầy đủ
        safe = email.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        result = await db.execute(select(User).where(User.email.ilike(f"{safe}@%", escape="\\")))
        matches = result.scalars().all()
        if len(matches) == 1:
            email = matches[0].email.lower()

    entry = _reset_codes.get(email)
    now = time.time()
    if not entry or entry[1] < now:
        _reset_codes.pop(email, None)
        raise HTTPException(status_code=400, detail="Mã không hợp lệ hoặc đã hết hạn")
    code, expires, attempts = entry
    if attempts <= 0:
        _reset_codes.pop(email, None)
        raise HTTPException(status_code=400, detail="Nhập sai quá số lần cho phép — yêu cầu mã mới")
    if not hmac.compare_digest(code, data.code.strip()):
        _reset_codes[email] = (code, expires, attempts - 1)
        raise HTTPException(status_code=400, detail="Mã không đúng")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Tài khoản không hợp lệ")

    user.password_hash = hash_password(data.new_password)
    _reset_codes.pop(email, None)
    await db.flush()
    return {"status": "ok", "message": "Đã đặt lại mật khẩu — đăng nhập bằng mật khẩu mới"}


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Email + password login → JWT."""
    client_ip = request.client.host if request.client else "unknown"
    _check_login_rate_limit(client_ip)

    identifier = data.email.strip()
    result = await db.execute(select(User).where(User.email == identifier))
    user = result.scalar_one_or_none()

    # Nội bộ: cho phép đăng nhập bằng phần trước @ (vd "admin" ↔ "admin@jamahome.vn").
    # Chỉ chạy khi người dùng gõ tên ngắn không có "@" và chưa khớp email đầy đủ.
    if user is None and "@" not in identifier and identifier:
        # Escape ký tự đại diện của LIKE để "adm%" không dò được nhiều tài khoản.
        safe = identifier.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        result = await db.execute(
            select(User).where(User.email.ilike(f"{safe}@%", escape="\\"))
        )
        matches = result.scalars().all()
        user = matches[0] if len(matches) == 1 else None

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
async def telegram_auth(
    data: TelegramAuth,
    db: AsyncSession = Depends(get_db),
    x_telegram_bot_secret: str = Header(default=""),
):
    """Telegram user_id → JWT. Chỉ bot (biết TELEGRAM_AUTH_SECRET) được gọi.

    Bảo mật: nếu không có bí mật chia sẻ, bất kỳ ai gọi được backend đều có thể
    mạo danh nhân viên chỉ bằng telegram_user_id. Do đó khi TELEGRAM_AUTH_SECRET
    được cấu hình, backend bắt buộc header X-Telegram-Bot-Secret khớp.
    """
    expected = settings.TELEGRAM_AUTH_SECRET
    if expected:
        if not hmac.compare_digest(x_telegram_bot_secret, expected):
            raise HTTPException(status_code=401, detail="Unauthorized")
    else:
        # Chưa cấu hình secret — hạn chế brute-force telegram_user_id
        _check_rate_limit(f"tg:{data.telegram_user_id}", max_attempts=10)

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
    if current_user.role not in ("admin", "accountant", "leader"):
        raise HTTPException(status_code=403, detail="Không có quyền xem danh sách nhân viên")
    result = await db.execute(select(User).where(User.is_active == True).order_by(User.full_name))
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]
