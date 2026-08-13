"""Phiên trượt (13/08/2026) — token qua nửa đời thì API kèm header X-Phien-Moi.

Đời token 12 tiếng. Người ĐANG dùng app không được rớt phiên giữa chừng:
- Token còn > nửa đời → KHÔNG gia hạn (đỡ ký token mới mỗi request).
- Token còn < nửa đời → header ``X-Phien-Moi`` chứa token mới, exp xa hơn,
  và token mới ký theo role HIỆN TẠI trong DB (đổi vai trò giữa phiên → lần
  gia hạn kế mang vai trò mới).
- Token đã chết → 401 như cũ, không gia hạn gì.
"""

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.config import get_settings
from tests.conftest import auth_header

settings = get_settings()


def _token_con(phut: int, user_id: str, role: str, department: str | None) -> str:
    """Ký token có exp còn đúng `phut` phút — mô phỏng token đã dùng lâu."""
    payload = {
        "sub": user_id,
        "role": role,
        "department": department,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=phut),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


@pytest.mark.asyncio
async def test_token_moi_khong_bi_gia_han(client, admin_user):
    """Token vừa cấp (còn nguyên 12h đời) → không có X-Phien-Moi."""
    resp = await client.get("/api/v1/auth/me", headers=auth_header(admin_user))
    assert resp.status_code == 200
    assert "x-phien-moi" not in resp.headers


@pytest.mark.asyncio
async def test_token_qua_nua_doi_duoc_gia_han(client, admin_user):
    """Token còn < nửa đời → header X-Phien-Moi chứa token mới dùng được, exp xa hơn."""
    token_cu = _token_con(60, str(admin_user.id), admin_user.role, admin_user.department)
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token_cu}"}
    )
    assert resp.status_code == 200
    token_moi = resp.headers.get("x-phien-moi")
    assert token_moi, "Token còn 1h/12h mà không được gia hạn"

    cu = jwt.decode(token_cu, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    moi = jwt.decode(token_moi, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert moi["exp"] > cu["exp"]
    assert moi["sub"] == str(admin_user.id)

    # Token mới phải dùng được ngay
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token_moi}"}
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_gia_han_ky_theo_role_hien_tai_trong_db(client, db_session, admin_user):
    """Đổi vai trò giữa phiên → token gia hạn mang vai trò MỚI, không chép token cũ."""
    token_cu = _token_con(60, str(admin_user.id), "data_entry", "SALES")  # token cũ ghi role cũ
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token_cu}"}
    )
    assert resp.status_code == 200
    token_moi = resp.headers.get("x-phien-moi")
    assert token_moi
    moi = jwt.decode(token_moi, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert moi["role"] == "admin"  # role thật trong DB, không phải "data_entry" từ token cũ


@pytest.mark.asyncio
async def test_token_chet_van_401_khong_gia_han(client, admin_user):
    """Token đã hết hạn → 401 như cũ (phiên trượt không cứu người bỏ máy quá 12h)."""
    token_chet = _token_con(-5, str(admin_user.id), admin_user.role, admin_user.department)
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token_chet}"}
    )
    assert resp.status_code == 401
    assert "x-phien-moi" not in resp.headers
