"""JWT authentication middleware."""

from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.services.llm_user_key import current_user_llm_key

settings = get_settings()
security = HTTPBearer()


def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: str, role: str, department: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": user_id,
        "role": role,
        "department": department,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn",
        )


async def get_current_user(
    response: Response,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency — extract and validate current user from JWT.

    Phiên trượt (13/08/2026): token sống 12 tiếng, nhưng người ĐANG dùng app thì
    không được để rớt phiên giữa chừng (trước đây làm tới tiếng 13 là mọi trang
    báo lỗi, phải đăng nhập lại). Khi token đã qua NỬA đời (còn < 6 tiếng), mỗi
    lời gọi API sẽ kèm token mới trong header ``X-Phien-Moi`` — frontend tự lưu
    đè, phiên cứ thế trượt dài theo giờ làm việc. Ai bỏ máy > 12 tiếng thì token
    hết hạn tự nhiên như cũ (không gia hạn được nữa vì 401 từ decode_token).
    """
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token thiếu user ID")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Tài khoản không tồn tại hoặc bị vô hiệu")

    # Khóa LLM cá nhân theo request: AI agents gọi trong request này sẽ ưu tiên
    # key của chính user (llm_config đọc contextvar, không cần truyền qua tham số)
    current_user_llm_key.set(user.llm_api_key or "")

    exp = payload.get("exp")
    if isinstance(exp, (int, float)):
        con_lai = exp - datetime.now(timezone.utc).timestamp()
        nua_doi = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60 / 2
        if 0 < con_lai < nua_doi:
            # Ký theo role/department HIỆN TẠI trong DB (không chép từ token cũ) —
            # đổi vai trò giữa phiên thì lần gia hạn kế tiếp mang đúng vai trò mới.
            response.headers["X-Phien-Moi"] = create_access_token(
                str(user.id), user.role, user.department
            )

    return user
