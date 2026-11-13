"""Phiên trượt — token sống 7 ngày, tự gia hạn, và huỷ được từ xa.

Đời token 7 ngày (13/11/2026, trước là 12 tiếng). Người mở app ít nhất 1 lần/tuần
không bao giờ phải đăng nhập lại:
- Token vừa cấp (< 24 tiếng tuổi) → KHÔNG gia hạn (đỡ ký token mới mỗi request).
- Token đã dùng quá 24 tiếng → header ``X-Phien-Moi`` chứa token mới, exp xa hơn,
  ký theo role HIỆN TẠI trong DB (đổi vai trò giữa phiên → lần gia hạn kế mang
  vai trò mới).
- Token cũ không có ``iat`` (cấp trước bản này) → vẫn dùng được, vẫn được gia hạn.
- Token đã chết → 401 như cũ, không gia hạn gì.

Huỷ phiên từ xa (bù rủi ro phiên dài): token có ``iat`` trước ``users.phien_tu``
bị 401. Mốc được ghi khi đổi/đặt lại mật khẩu và ở «Đăng xuất các thiết bị khác»;
thiết bị đang thao tác nhận token mới qua ``X-Phien-Moi`` nên không bị văng.
"""

import time
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.api.auth import _reset_codes
from app.config import get_settings
from tests.conftest import auth_header

settings = get_settings()

ME = "/api/v1/auth/me"
MOT_NGAY = 24 * 3600


def _token_con(
    phut: int,
    user_id: str,
    role: str,
    department: str | None,
    tuoi_giay: int | None = None,
) -> str:
    """Ký token có exp còn đúng `phut` phút — mô phỏng token đã dùng lâu.

    `tuoi_giay` = token được cấp cách đây bao nhiêu giây (ghi vào ``iat``).
    Bỏ trống → token kiểu cũ, không có ``iat``.
    """
    bay_gio = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "department": department,
        "exp": bay_gio + timedelta(minutes=phut),
    }
    if tuoi_giay is not None:
        payload["iat"] = int(bay_gio.timestamp()) - tuoi_giay
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _token_tuoi(user, tuoi_giay: int) -> str:
    """Token của `user` đã cấp cách đây `tuoi_giay` giây, đời còn lại đúng theo cấu hình."""
    con_phut = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES - tuoi_giay // 60
    return _token_con(con_phut, str(user.id), user.role, user.department, tuoi_giay)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _giai_ma(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ── Gia hạn ────────────────────────────────────────────────────────────────


def test_doi_token_mac_dinh_la_7_ngay():
    assert settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES == 7 * 24 * 60


@pytest.mark.asyncio
async def test_token_moi_co_iat(admin_user):
    token = auth_header(admin_user)["Authorization"].split(" ", 1)[1]
    payload = _giai_ma(token)
    assert isinstance(payload["iat"], int)
    assert abs(payload["iat"] - time.time()) < 5
    assert payload["exp"] - payload["iat"] == settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60


@pytest.mark.asyncio
async def test_token_moi_khong_bi_gia_han(client, admin_user):
    """Token vừa cấp → không có X-Phien-Moi."""
    resp = await client.get(ME, headers=auth_header(admin_user))
    assert resp.status_code == 200
    assert "x-phien-moi" not in resp.headers


@pytest.mark.asyncio
async def test_token_dung_chua_toi_24_tieng_khong_gia_han(client, admin_user):
    """Dùng 20 tiếng rồi vẫn chưa ký lại — mỗi người tối đa 1 token/ngày."""
    resp = await client.get(ME, headers=_bearer(_token_tuoi(admin_user, 20 * 3600)))
    assert resp.status_code == 200
    assert "x-phien-moi" not in resp.headers


@pytest.mark.asyncio
async def test_token_dung_2_ngay_duoc_gia_han(client, admin_user):
    """Token đã dùng 2 ngày (còn 5 ngày) → header X-Phien-Moi, exp xa hơn, dùng được ngay."""
    token_cu = _token_tuoi(admin_user, 2 * MOT_NGAY)
    resp = await client.get(ME, headers=_bearer(token_cu))
    assert resp.status_code == 200
    token_moi = resp.headers.get("x-phien-moi")
    assert token_moi, "Token đã dùng 2 ngày mà không được gia hạn"

    cu, moi = _giai_ma(token_cu), _giai_ma(token_moi)
    assert moi["exp"] > cu["exp"]
    assert moi["iat"] > cu["iat"]
    assert moi["sub"] == str(admin_user.id)

    resp = await client.get(ME, headers=_bearer(token_moi))
    assert resp.status_code == 200
    assert "x-phien-moi" not in resp.headers


@pytest.mark.asyncio
async def test_token_cu_khong_iat_van_duoc_gia_han(client, admin_user):
    """Token cấp trước bản này (không có iat, còn 1 tiếng) → vẫn vào được và được gia hạn."""
    token_cu = _token_con(60, str(admin_user.id), admin_user.role, admin_user.department)
    resp = await client.get(ME, headers=_bearer(token_cu))
    assert resp.status_code == 200
    token_moi = resp.headers.get("x-phien-moi")
    assert token_moi, "Token kiểu cũ sắp hết hạn mà không được gia hạn"

    cu, moi = _giai_ma(token_cu), _giai_ma(token_moi)
    assert moi["exp"] > cu["exp"]
    assert "iat" in moi

    resp = await client.get(ME, headers=_bearer(token_moi))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_gia_han_ky_theo_role_hien_tai_trong_db(client, db_session, admin_user):
    """Token cũ mang role lỗi thời → token gia hạn ký theo role đang có trong DB."""
    token_cu = _token_con(
        60, str(admin_user.id), "data_entry", "SALES", tuoi_giay=2 * MOT_NGAY
    )
    resp = await client.get(ME, headers=_bearer(token_cu))
    assert resp.status_code == 200
    moi = _giai_ma(resp.headers["x-phien-moi"])
    assert moi["role"] == "admin"
    assert moi["department"] == admin_user.department


@pytest.mark.asyncio
async def test_token_chet_van_401_khong_gia_han(client, admin_user):
    """Token đã hết hạn → 401, không có X-Phien-Moi (bỏ máy quá 7 ngày thì đăng nhập lại)."""
    token = _token_con(
        -5, str(admin_user.id), admin_user.role, admin_user.department, tuoi_giay=8 * MOT_NGAY
    )
    resp = await client.get(ME, headers=_bearer(token))
    assert resp.status_code == 401
    assert "x-phien-moi" not in resp.headers


# ── Huỷ phiên từ xa (users.phien_tu) ───────────────────────────────────────


@pytest.mark.asyncio
async def test_token_cap_truoc_moc_phien_tu_bi_401(client, db_session, admin_user):
    """Token có iat trước users.phien_tu → 401, kể cả khi còn hạn và đủ tuổi gia hạn."""
    token_cu = _token_tuoi(admin_user, 2 * MOT_NGAY)
    admin_user.phien_tu = datetime.now(timezone.utc).replace(tzinfo=None)
    await db_session.commit()

    resp = await client.get(ME, headers=_bearer(token_cu))
    assert resp.status_code == 401
    assert "đăng xuất" in resp.json()["detail"]
    assert "x-phien-moi" not in resp.headers


@pytest.mark.asyncio
async def test_token_khong_iat_bi_401_sau_khi_co_moc(client, db_session, admin_user):
    """Đã có mốc huỷ phiên thì token kiểu cũ (không iat) cũng bị từ chối — không lách được."""
    token_cu = _token_con(60, str(admin_user.id), admin_user.role, admin_user.department)
    admin_user.phien_tu = datetime.now(timezone.utc).replace(tzinfo=None)
    await db_session.commit()

    resp = await client.get(ME, headers=_bearer(token_cu))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_cap_sau_moc_phien_tu_van_dung_duoc(client, db_session, admin_user):
    """Mốc huỷ ở quá khứ không chặn token cấp sau đó (đăng nhập lại là vào được)."""
    admin_user.phien_tu = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None)
    await db_session.commit()

    resp = await client.get(ME, headers=auth_header(admin_user))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_moc_phien_tu_cua_nguoi_nay_khong_dung_nguoi_khac(
    client, db_session, admin_user, sales_user
):
    admin_user.phien_tu = datetime.now(timezone.utc).replace(tzinfo=None)
    await db_session.commit()

    resp = await client.get(ME, headers=_bearer(_token_tuoi(sales_user, 3600)))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_dang_xuat_thiet_bi_khac(client, admin_user):
    """Máy A bấm «Đăng xuất các thiết bị khác»: máy B (token cũ) văng, máy A ở lại."""
    may_a = _token_tuoi(admin_user, 3600)
    may_b = _token_tuoi(admin_user, 2 * 3600)

    resp = await client.post("/api/v1/auth/logout-all", headers=_bearer(may_a))
    assert resp.status_code == 200
    token_moi = resp.headers.get("x-phien-moi")
    assert token_moi
    assert resp.json()["access_token"] == token_moi

    assert (await client.get(ME, headers=_bearer(may_b))).status_code == 401
    assert (await client.get(ME, headers=_bearer(may_a))).status_code == 401
    assert (await client.get(ME, headers=_bearer(token_moi))).status_code == 200


@pytest.mark.asyncio
async def test_dang_xuat_thiet_bi_khac_can_dang_nhap(client):
    resp = await client.post("/api/v1/auth/logout-all")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_doi_mat_khau_huy_token_cu(client, admin_user):
    """Đổi mật khẩu → token cũ ở máy khác chết; máy đang đổi nhận token mới dùng được."""
    may_a = _token_tuoi(admin_user, 3600)
    may_b = _token_tuoi(admin_user, 2 * 3600)

    resp = await client.post(
        "/api/v1/auth/change-password",
        headers=_bearer(may_a),
        json={"old_password": "admin123", "new_password": "mat-khau-moi-1"},
    )
    assert resp.status_code == 200
    token_moi = resp.headers.get("x-phien-moi")
    assert token_moi, "Đổi mật khẩu xong phải cấp token mới cho máy đang dùng"

    assert (await client.get(ME, headers=_bearer(may_b))).status_code == 401
    assert (await client.get(ME, headers=_bearer(token_moi))).status_code == 200


@pytest.mark.asyncio
async def test_doi_mat_khau_sai_mat_khau_cu_khong_huy_phien(client, admin_user):
    may_b = _token_tuoi(admin_user, 2 * 3600)
    resp = await client.post(
        "/api/v1/auth/change-password",
        headers=_bearer(_token_tuoi(admin_user, 3600)),
        json={"old_password": "sai-mat-khau", "new_password": "mat-khau-moi-1"},
    )
    assert resp.status_code == 400
    assert admin_user.phien_tu is None
    assert (await client.get(ME, headers=_bearer(may_b))).status_code == 200


@pytest.mark.asyncio
async def test_dat_lai_mat_khau_bang_ma_huy_token_cu(client, admin_user):
    """Quên mật khẩu → đặt lại bằng mã Telegram: mọi token cũ chết."""
    token_cu = _token_tuoi(admin_user, 3600)
    _reset_codes[admin_user.email] = ("123456", time.time() + 600, 5)

    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"email": admin_user.email, "code": "123456", "new_password": "mat-khau-moi-2"},
    )
    assert resp.status_code == 200
    assert (await client.get(ME, headers=_bearer(token_cu))).status_code == 401


@pytest.mark.asyncio
async def test_admin_dat_mat_khau_cho_nguoi_khac_huy_token_nguoi_do(
    client, admin_user, sales_user
):
    """Admin đặt mật khẩu mới cho nhân viên (mất máy) → token của nhân viên chết, admin không sao."""
    token_sale = _token_tuoi(sales_user, 3600)
    token_admin = _token_tuoi(admin_user, 3600)

    resp = await client.put(
        f"/api/v1/users/{sales_user.id}",
        headers=_bearer(token_admin),
        json={"password": "mat-khau-moi-3"},
    )
    assert resp.status_code == 200, resp.text
    assert "x-phien-moi" not in resp.headers

    assert (await client.get(ME, headers=_bearer(token_sale))).status_code == 401
    assert (await client.get(ME, headers=_bearer(token_admin))).status_code == 200


@pytest.mark.asyncio
async def test_admin_tu_dat_mat_khau_minh_qua_trang_tai_khoan_khong_bi_vang(client, admin_user):
    """Admin tự đổi mật khẩu của mình ở trang Tài khoản → máy đang dùng nhận token mới."""
    token_cu = _token_tuoi(admin_user, 3600)
    resp = await client.put(
        f"/api/v1/users/{admin_user.id}",
        headers=_bearer(token_cu),
        json={"password": "mat-khau-moi-4"},
    )
    assert resp.status_code == 200, resp.text
    token_moi = resp.headers.get("x-phien-moi")
    assert token_moi

    assert (await client.get(ME, headers=_bearer(token_cu))).status_code == 401
    assert (await client.get(ME, headers=_bearer(token_moi))).status_code == 200
