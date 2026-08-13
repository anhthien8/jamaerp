"""Khóa AI cá nhân (13/08/2026) — users.llm_api_key + ưu tiên trước key hệ thống.

Phủ:
- API /ai-settings/my-key: GET/PUT/xóa cho MỌI vai trò, validate key ngắn, 401 khi chưa đăng nhập.
- Không lộ key: /auth/me, /users, /ai-settings/my-key chỉ trả dạng che.
- llm_complete: key cá nhân đứng TRƯỚC key hệ thống; cá nhân lỗi → rơi về hệ thống;
  không có key cá nhân → dùng hệ thống; trùng key → chỉ thử một lần.
- Background task (worker/bot): contextvar mặc định "" → dùng key hệ thống.
- Key cá nhân CHỈ dùng với model groq/ (không gửi sang provider khác).
- /ai-settings/test (admin) test đúng key HỆ THỐNG, bỏ qua key cá nhân của admin.
- Auth set contextvar theo user của request.
"""

import asyncio

import pytest

from app.services import llm_config as llm_config_module
from app.services.llm_user_key import current_user_llm_key

from tests.conftest import auth_header

PERSONAL_KEY = "gsk_personal_key_1234567890abcd"
SYSTEM_KEY = "gsk_system_key_0987654321dcba"


class _FakeResponse:
    """Đủ hình dạng cho chỗ đọc response.choices[0].message.content + .model."""

    model = "groq/fake-model"

    class _Choice:
        class _Message:
            content = "OK"

        message = _Message()

    choices = [_Choice()]


def _capture_acompletion(calls: list[dict], fail_keys: set[str] | None = None):
    """Fake acompletion ghi lại api_key mỗi lần gọi; raise nếu key nằm trong fail_keys."""

    async def fake(**params):
        calls.append(params)
        if fail_keys and params.get("api_key") in fail_keys:
            raise RuntimeError("simulated: key bị từ chối")
        return _FakeResponse()

    return fake


def _fake_config(**overrides):
    config = {
        "llm_model": "groq/test-model",
        "llm_api_key": SYSTEM_KEY,
        "llm_fallback_model": "",
        "llm_fallback_api_key": "",
    }
    config.update(overrides)

    async def fake_get_llm_config(db=None):
        return config

    return fake_get_llm_config


# ---------------------------------------------------------------------------
# API /ai-settings/my-key — mọi vai trò
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_my_key_crud_moi_vai_tro(client, sales_user):
    """Vai trò thường (không phải admin) tự quản lý key của mình: xem/lưu/xóa."""
    headers = auth_header(sales_user)

    # Chưa có key
    resp = await client.get("/api/v1/ai-settings/my-key", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"set": False, "masked": ""}

    # Lưu key → chỉ trả dạng che, không bao giờ trả key đầy đủ
    resp = await client.put(
        "/api/v1/ai-settings/my-key", json={"api_key": PERSONAL_KEY}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["set"] is True
    assert body["masked"] == f"{PERSONAL_KEY[:4]}****{PERSONAL_KEY[-4:]}"
    assert PERSONAL_KEY not in resp.text

    # GET lại thấy trạng thái đã lưu
    resp = await client.get("/api/v1/ai-settings/my-key", headers=headers)
    assert resp.json()["set"] is True

    # Xóa key (gửi chuỗi rỗng)
    resp = await client.put("/api/v1/ai-settings/my-key", json={"api_key": ""}, headers=headers)
    assert resp.json() == {"set": False, "masked": ""}


@pytest.mark.asyncio
async def test_my_key_validate_va_auth(client, sales_user):
    headers = auth_header(sales_user)

    # Key quá ngắn → 400
    resp = await client.put("/api/v1/ai-settings/my-key", json={"api_key": "abc"}, headers=headers)
    assert resp.status_code == 400

    # Key không phải Groq (không bắt đầu gsk_) → 400
    resp = await client.put(
        "/api/v1/ai-settings/my-key",
        json={"api_key": "sk-openai-key-1234567890"},
        headers=headers,
    )
    assert resp.status_code == 400

    # Chưa đăng nhập → 401
    resp = await client.get("/api/v1/ai-settings/my-key")
    assert resp.status_code == 401

    # Chưa lưu key mà test → 400 báo rõ
    resp = await client.post("/api/v1/ai-settings/my-key/test", headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_key_khong_lo_qua_api_users(client, db_session, admin_user, sales_user):
    """UserResponse là schema liệt kê field tường minh — key không được rò qua đó."""
    sales_user.llm_api_key = PERSONAL_KEY
    await db_session.commit()

    resp = await client.get("/api/v1/auth/me", headers=auth_header(sales_user))
    assert resp.status_code == 200
    assert PERSONAL_KEY not in resp.text

    resp = await client.get("/api/v1/users", headers=auth_header(admin_user))
    assert resp.status_code == 200
    assert PERSONAL_KEY not in resp.text


# ---------------------------------------------------------------------------
# llm_complete — thứ tự ưu tiên key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_complete_uu_tien_key_ca_nhan(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(llm_config_module, "get_llm_config", _fake_config())
    monkeypatch.setattr(llm_config_module, "acompletion", _capture_acompletion(calls))

    token = current_user_llm_key.set(PERSONAL_KEY)
    try:
        await llm_config_module.llm_complete(messages=[{"role": "user", "content": "hi"}])
    finally:
        current_user_llm_key.reset(token)

    # Thành công ngay lần đầu với key cá nhân — không đụng key hệ thống
    assert len(calls) == 1
    assert calls[0]["api_key"] == PERSONAL_KEY


@pytest.mark.asyncio
async def test_llm_complete_key_ca_nhan_loi_roi_ve_he_thong(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(llm_config_module, "get_llm_config", _fake_config())
    monkeypatch.setattr(
        llm_config_module, "acompletion", _capture_acompletion(calls, fail_keys={PERSONAL_KEY})
    )

    token = current_user_llm_key.set(PERSONAL_KEY)
    try:
        response = await llm_config_module.llm_complete(
            messages=[{"role": "user", "content": "hi"}]
        )
    finally:
        current_user_llm_key.reset(token)

    # Lần 1 key cá nhân (bị từ chối) → lần 2 key hệ thống, user không bị kẹt
    assert [c["api_key"] for c in calls] == [PERSONAL_KEY, SYSTEM_KEY]
    assert response.choices[0].message.content == "OK"


@pytest.mark.asyncio
async def test_llm_complete_khong_co_key_ca_nhan(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(llm_config_module, "get_llm_config", _fake_config())
    monkeypatch.setattr(llm_config_module, "acompletion", _capture_acompletion(calls))

    await llm_config_module.llm_complete(messages=[{"role": "user", "content": "hi"}])

    assert len(calls) == 1
    assert calls[0]["api_key"] == SYSTEM_KEY


@pytest.mark.asyncio
async def test_llm_complete_key_trung_chi_thu_mot_lan(monkeypatch):
    """User dán đúng key hệ thống vào ô cá nhân → không thử hai lần cùng một key."""
    calls: list[dict] = []
    monkeypatch.setattr(llm_config_module, "get_llm_config", _fake_config())
    monkeypatch.setattr(
        llm_config_module, "acompletion", _capture_acompletion(calls, fail_keys={SYSTEM_KEY})
    )

    token = current_user_llm_key.set(SYSTEM_KEY)
    try:
        with pytest.raises(RuntimeError):
            await llm_config_module.llm_complete(
                messages=[{"role": "user", "content": "hi"}]
            )
    finally:
        current_user_llm_key.reset(token)

    assert len(calls) == 1


@pytest.mark.asyncio
async def test_worker_nen_dung_key_he_thong(monkeypatch):
    """Task nền (worker/bot) không đi qua auth → contextvar giữ mặc định "" → key hệ thống."""
    calls: list[dict] = []
    monkeypatch.setattr(llm_config_module, "get_llm_config", _fake_config())
    monkeypatch.setattr(llm_config_module, "acompletion", _capture_acompletion(calls))

    async def background_job():
        assert current_user_llm_key.get() == ""
        await llm_config_module.llm_complete(messages=[{"role": "user", "content": "hi"}])

    await asyncio.create_task(background_job())

    assert len(calls) == 1
    assert calls[0]["api_key"] == SYSTEM_KEY


@pytest.mark.asyncio
async def test_key_ca_nhan_khong_dung_cho_model_khac_groq(monkeypatch):
    """Finding review 14/08: key cá nhân là key GROQ — model hệ thống đổi sang
    Gemini/OpenRouter thì TUYỆT ĐỐI không gửi key cá nhân sang provider đó."""
    calls: list[dict] = []
    monkeypatch.setattr(
        llm_config_module,
        "get_llm_config",
        _fake_config(llm_model="gemini/gemini-2.0-flash"),
    )
    monkeypatch.setattr(llm_config_module, "acompletion", _capture_acompletion(calls))

    token = current_user_llm_key.set(PERSONAL_KEY)
    try:
        await llm_config_module.llm_complete(messages=[{"role": "user", "content": "hi"}])
    finally:
        current_user_llm_key.reset(token)

    # Chỉ 1 attempt bằng key hệ thống — key cá nhân không rời khỏi nhà
    assert len(calls) == 1
    assert calls[0]["api_key"] == SYSTEM_KEY


# ---------------------------------------------------------------------------
# End-to-end qua HTTP: auth set contextvar cho request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_set_contextvar_theo_user(db_session, sales_user):
    """get_current_user phải nạp key cá nhân của user vào contextvar."""
    from fastapi import Response
    from fastapi.security import HTTPAuthorizationCredentials

    from app.middleware.auth import create_access_token, get_current_user

    sales_user.llm_api_key = PERSONAL_KEY
    await db_session.commit()

    creds = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=create_access_token(
            str(sales_user.id), sales_user.role, sales_user.department
        ),
    )
    user = await get_current_user(Response(), creds, db_session)
    assert user.id == sales_user.id
    assert current_user_llm_key.get() == PERSONAL_KEY
    current_user_llm_key.set("")  # dọn context cho test sau


@pytest.mark.asyncio
async def test_nut_test_he_thong_dung_key_he_thong(client, db_session, admin_user, monkeypatch):
    """Finding review 14/08: POST /ai-settings/test là công cụ chẩn đoán key CHUNG —
    admin có key cá nhân vẫn phải test bằng key hệ thống (không thì key chung chết
    mà nút test vẫn báo ok, nhân viên + worker nền âm thầm mất AI)."""
    admin_user.llm_api_key = PERSONAL_KEY
    await db_session.commit()

    calls: list[dict] = []
    monkeypatch.setattr(llm_config_module, "get_llm_config", _fake_config())
    monkeypatch.setattr(llm_config_module, "acompletion", _capture_acompletion(calls))

    resp = await client.post("/api/v1/ai-settings/test", headers=auth_header(admin_user))
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    assert len(calls) == 1
    assert calls[0]["api_key"] == SYSTEM_KEY
    assert PERSONAL_KEY not in resp.text


@pytest.mark.asyncio
async def test_my_key_test_goi_dung_key_ca_nhan(client, db_session, sales_user, monkeypatch):
    """POST /my-key/test gọi litellm trực tiếp với ĐÚNG key cá nhân (không rơi về hệ thống)."""
    sales_user.llm_api_key = PERSONAL_KEY
    await db_session.commit()

    calls: list[dict] = []
    import litellm

    monkeypatch.setattr(litellm, "acompletion", _capture_acompletion(calls))

    resp = await client.post("/api/v1/ai-settings/my-key/test", headers=auth_header(sales_user))
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert len(calls) == 1
    assert calls[0]["api_key"] == PERSONAL_KEY


@pytest.mark.asyncio
async def test_my_key_test_ep_model_groq(client, db_session, sales_user, monkeypatch):
    """Finding review 14/08: model hệ thống không phải Groq → /my-key/test phải
    tự chuyển sang model Groq, không gửi key cá nhân tới provider khác."""
    sales_user.llm_api_key = PERSONAL_KEY
    await db_session.commit()

    calls: list[dict] = []
    import litellm

    from app.api import ai_settings as ai_settings_module

    monkeypatch.setattr(litellm, "acompletion", _capture_acompletion(calls))
    monkeypatch.setattr(
        ai_settings_module,
        "get_llm_config",
        _fake_config(llm_model="openrouter/meta-llama/llama-3.3-70b-instruct:free"),
    )

    resp = await client.post("/api/v1/ai-settings/my-key/test", headers=auth_header(sales_user))
    assert resp.status_code == 200
    assert len(calls) == 1
    assert calls[0]["model"].startswith("groq/")
    assert calls[0]["api_key"] == PERSONAL_KEY
