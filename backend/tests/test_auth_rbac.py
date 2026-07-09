"""Tests for Auth API + RBAC — login, JWT, rate limiting, role gates."""

import time

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.middleware.auth import create_access_token, decode_token, hash_password, verify_password
from app.models.user import User
from tests.conftest import auth_header, _uid

_settings = get_settings()


# ── Password hashing ──────────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_and_verify(self):
        raw = "test_password_123"
        hashed = hash_password(raw)
        assert verify_password(raw, hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_different_hashes(self):
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        # Salt is random, so hashes should differ
        assert h1 != h2


# ── JWT token creation & decode ──────────────────────────────────────────

class TestJWTTokens:
    def test_create_and_decode_token(self):
        user_id = "test-user-id-123"
        token = create_access_token(user_id, "admin", "EXEC")
        payload = decode_token(token)
        assert payload["sub"] == user_id
        assert payload["role"] == "admin"
        assert payload["department"] == "EXEC"
        assert "exp" in payload

    def test_invalid_token_raises(self):
        import pytest as _pytest
        from fastapi import HTTPException
        with _pytest.raises(HTTPException) as exc_info:
            decode_token("totally.invalid.token")
        assert exc_info.value.status_code == 401


# ── POST /api/v1/auth/login ───────────────────────────────────────────────

@pytest.mark.asyncio
class TestLogin:
    async def test_login_success(self, client: AsyncClient, admin_user: User):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "admin123"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["user"]["role"] == "admin"
        assert body["user"]["email"] == "admin@test.com"

    async def test_login_wrong_password(self, client: AsyncClient, admin_user: User):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "wrong_password"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_email(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@example.com", "password": "whatever"},
        )
        assert resp.status_code == 401

    async def test_login_disabled_user(self, db_session: AsyncClient, client: AsyncClient):
        # Create a disabled user
        user = User(
            id=_uid(),
            full_name="Disabled User",
            email="disabled@test.com",
            password_hash=hash_password("pass123"),
            role="data_entry",
            department="SALES",
            is_active=False,
        )
        db_session.add(user)
        await db_session.commit()

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "disabled@test.com", "password": "pass123"},
        )
        assert resp.status_code == 403

    async def test_login_rate_limiting(self, client: AsyncClient, admin_user: User):
        """After 5 failed attempts, 6th should get 429."""
        for _ in range(5):
            await client.post(
                "/api/v1/auth/login",
                json={"email": "admin@test.com", "password": "wrong"},
            )
        # 6th attempt should be rate-limited
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "wrong"},
        )
        assert resp.status_code == 429


# ── GET /api/v1/auth/me ──────────────────────────────────────────────────

@pytest.mark.asyncio
class TestGetMe:
    async def test_get_me_returns_user(self, client: AsyncClient, admin_user: User):
        resp = await client.get("/api/v1/auth/me", headers=auth_header(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "admin@test.com"
        assert body["role"] == "admin"

    async def test_get_me_no_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code in (401, 403)

    async def test_get_me_invalid_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert resp.status_code == 401


# ── GET /api/v1/auth/users ───────────────────────────────────────────────

@pytest.mark.asyncio
class TestListUsers:
    async def test_list_users_returns_array(self, client: AsyncClient, admin_user: User):
        resp = await client.get("/api/v1/auth/users", headers=auth_header(admin_user))
        assert resp.status_code == 200
        users = resp.json()
        assert isinstance(users, list)
        assert any(u["email"] == "admin@test.com" for u in users)

    async def test_list_users_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/users")
        assert resp.status_code in (401, 403)


# ── POST /api/v1/auth/telegram ────────────────────────────────────────────

_TG_SECRET_HEADER = (
    {"X-Telegram-Bot-Secret": _settings.TELEGRAM_AUTH_SECRET}
    if _settings.TELEGRAM_AUTH_SECRET
    else {}
)


@pytest.mark.asyncio
class TestTelegramAuth:
    async def test_telegram_auth_success(self, client: AsyncClient, admin_user: User):
        resp = await client.post(
            "/api/v1/auth/telegram",
            json={"telegram_user_id": 900001, "telegram_username": "admin_tg"},
            headers=_TG_SECRET_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body

    async def test_telegram_auth_unknown_user(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/telegram",
            json={"telegram_user_id": 999999},
            headers=_TG_SECRET_HEADER,
        )
        assert resp.status_code == 404

    async def test_telegram_auth_disabled_user(self, db_session: AsyncClient, client: AsyncClient):
        user = User(
            id=_uid(),
            full_name="Disabled TG",
            email="tg_disabled@test.com",
            password_hash=hash_password("pass"),
            role="data_entry",
            department="SALES",
            is_active=False,
            telegram_user_id=888888,
        )
        db_session.add(user)
        await db_session.commit()

        resp = await client.post(
            "/api/v1/auth/telegram",
            json={"telegram_user_id": 888888},
            headers=_TG_SECRET_HEADER,
        )
        assert resp.status_code == 403
