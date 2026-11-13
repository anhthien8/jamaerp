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


# Token đã dùng quá ngần này giây thì được ký lại (tối đa 1 lần/ngày/người).
_GIA_HAN_SAU_GIAY = 24 * 3600


def create_access_token(user_id: str, role: str, department: str) -> str:
    luc_cap = datetime.now(timezone.utc)
    expire = luc_cap + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "role": role,
        "department": department,
        # iat (giây, số nguyên): mốc cấp token — dùng để gia hạn theo tuổi token
        # và để từ chối token cấp trước users.phien_tu.
        "iat": int(luc_cap.timestamp()),
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def moc_phien_moi() -> datetime:
    """Mốc «bây giờ» để ghi vào users.phien_tu — datetime naive, giờ UTC."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _phien_tu_epoch(user: User) -> int | None:
    """users.phien_tu đổi ra epoch giây (làm tròn xuống), None nếu chưa từng đặt.

    Làm tròn xuống để token cấp NGAY SAU khi đặt mốc (cùng giây đó) vẫn hợp lệ —
    iat của JWT chỉ chính xác tới giây.
    """
    moc = getattr(user, "phien_tu", None)
    if moc is None:
        return None
    if moc.tzinfo is None:
        moc = moc.replace(tzinfo=timezone.utc)
    return int(moc.timestamp())


def cat_phien_cu(user: User, response: Response | None = None) -> str | None:
    """Huỷ mọi token đã cấp cho ``user`` trước lúc này (đổi mật khẩu, đăng xuất thiết bị khác).

    Truyền ``response`` khi chính người đó đang thao tác: thiết bị đang dùng nhận
    token mới qua header ``X-Phien-Moi`` (frontend tự lưu đè) nên không bị văng ra.
    Trả về token mới đó, hoặc None nếu không cấp.
    """
    user.phien_tu = moc_phien_moi()
    if response is None:
        return None
    token = create_access_token(str(user.id), user.role, user.department)
    response.headers["X-Phien-Moi"] = token
    return token


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

    Phiên trượt (13/08/2026, nới 13/11/2026): token sống 7 ngày. Khi token đã dùng
    quá 24 tiếng, lời gọi API kế tiếp kèm token mới trong header ``X-Phien-Moi`` —
    frontend tự lưu đè, nên ai mở app ít nhất 1 lần/tuần thì không phải đăng nhập
    lại. Bỏ máy quá 7 ngày thì token hết hạn tự nhiên (401 từ decode_token).

    Huỷ phiên: ``users.phien_tu`` là mốc «chỉ nhận token cấp từ lúc này». Đổi mật
    khẩu / đặt lại mật khẩu / «Đăng xuất các thiết bị khác» ghi mốc đó; token có
    ``iat`` trước mốc → 401. Token cũ không có ``iat`` (cấp trước bản 13/11) chỉ bị
    từ chối khi người đó đã có mốc; chưa có mốc thì dùng tới khi hết hạn.
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

    bay_gio = datetime.now(timezone.utc).timestamp()
    iat = payload.get("iat")
    co_iat = isinstance(iat, (int, float)) and not isinstance(iat, bool)

    moc = _phien_tu_epoch(user)
    if moc is not None and (not co_iat or iat < moc):
        raise HTTPException(
            status_code=401, detail="Phiên đã bị đăng xuất, vui lòng đăng nhập lại"
        )

    # Gia hạn: token đã dùng quá 24 tiếng (đời token ngắn hơn 2 ngày thì lấy nửa đời).
    tong = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    nguong = min(_GIA_HAN_SAU_GIAY, tong / 2)
    exp = payload.get("exp")
    if co_iat:
        can_gia_han = bay_gio - iat > nguong
    elif isinstance(exp, (int, float)):
        # Token cũ không có iat: suy tuổi từ thời gian còn lại. Token 12 tiếng cấp
        # trước bản 13/11 luôn rơi vào đây → lần gọi đầu được đổi sang token 7 ngày.
        can_gia_han = 0 < exp - bay_gio < tong - nguong
    else:
        can_gia_han = False
    if can_gia_han:
        # Ký theo role/department HIỆN TẠI trong DB (không chép từ token cũ) —
        # đổi vai trò giữa phiên thì lần gia hạn kế tiếp mang đúng vai trò mới.
        response.headers["X-Phien-Moi"] = create_access_token(
            str(user.id), user.role, user.department
        )

    return user
