"""Tests backup_service — chuyển URL Postgres, gửi Telegram, xử lý lỗi.

Không cần pg_dump/Telegram thật: mock asyncio.create_subprocess_exec và httpx.
Bao phủ hợp đồng: đổi URL asyncpg→libpq, thiếu chat_id, file quá lớn,
gửi sendDocument đúng chat_id + caption, pg_dump lỗi không lộ mật khẩu,
và ghi backup_last_* cả khi lỗi.
"""

import pytest

from app.services import backup_service
from app.services.backup_service import (
    MAX_TELEGRAM_MB,
    _pg_libpq_url,
    get_setting,
    run_backup,
    set_setting,
)


# ── (a) Chuyển đổi URL asyncpg → libpq ───────────────────────────────────

class TestPgUrlConversion:
    def test_strips_asyncpg_driver(self):
        assert _pg_libpq_url("postgresql+asyncpg://u:p@h:5432/db") == "postgresql://u:p@h:5432/db"

    def test_postgres_scheme_normalized(self):
        assert _pg_libpq_url("postgres://u:p@h:5432/db").startswith("postgresql://")

    def test_ssl_require_becomes_sslmode(self):
        out = _pg_libpq_url("postgresql+asyncpg://u:p@h:5432/db?ssl=require")
        assert "sslmode=require" in out
        assert "ssl=require" not in out

    def test_ssl_true_maps_to_require(self):
        assert "sslmode=require" in _pg_libpq_url("postgresql+asyncpg://u:p@h/db?ssl=true")

    def test_ssl_disable_mapping(self):
        assert "sslmode=disable" in _pg_libpq_url("postgresql+asyncpg://u:p@h/db?ssl=false")

    def test_preserves_password_and_host(self):
        out = _pg_libpq_url("postgresql+asyncpg://user:s3cr3t@db.internal:5432/jama?ssl=require")
        assert "user:s3cr3t@db.internal:5432/jama" in out
        assert "sslmode=require" in out


# ── Helper: giả lập bước tạo file backup đã thành công ───────────────────

def _fake_created_file(tmp_path, size_mb: float, name: str = "jama-crm-20260807-050000.dump"):
    fake = tmp_path / name
    fake.write_bytes(b"backup-bytes")

    async def _create(now_vn):
        return fake, "PostgreSQL", size_mb

    return fake, _create


# ── (b) Thiếu chat_id → status error + ghi last_* ────────────────────────

@pytest.mark.asyncio
async def test_missing_chat_id_returns_error(db_session, tmp_path, monkeypatch):
    fake, fake_create = _fake_created_file(tmp_path, 1.2)
    monkeypatch.setattr(backup_service, "_create_backup_file", fake_create)
    monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path)

    result = await run_backup(db_session)

    assert result["status"] == "error"
    assert "Chưa cấu hình nhóm Telegram" in result["reason"]
    # (f) backup_last_* được ghi đầy đủ kể cả khi lỗi
    assert await get_setting(db_session, "backup_last_status") == "error"
    assert await get_setting(db_session, "backup_last_run_at")
    assert await get_setting(db_session, "backup_last_detail") == result["reason"]
    assert await get_setting(db_session, "backup_last_size_mb") == "1.2"


# ── (c) File > 49MB → không gửi, status error, file vẫn giữ local ────────

@pytest.mark.asyncio
async def test_oversize_file_not_sent(db_session, tmp_path, monkeypatch):
    fake, fake_create = _fake_created_file(tmp_path, float(MAX_TELEGRAM_MB + 10))
    monkeypatch.setattr(backup_service, "_create_backup_file", fake_create)
    monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path)
    await set_setting(db_session, "backup_telegram_chat_id", "-100999")
    monkeypatch.setattr(backup_service.settings, "TELEGRAM_BOT_TOKEN", "111:tok")

    sent = {"count": 0}

    async def _should_not_call(*args, **kwargs):
        sent["count"] += 1

    monkeypatch.setattr(backup_service, "_telegram_send_document", _should_not_call)

    result = await run_backup(db_session)

    assert result["status"] == "error"
    assert str(MAX_TELEGRAM_MB) in result["reason"]
    assert sent["count"] == 0            # KHÔNG gọi sendDocument
    assert fake.exists()                 # file vẫn được giữ trên máy chủ
    assert await get_setting(db_session, "backup_last_status") == "error"


# ── (d) Thành công → sendDocument đúng chat_id + có caption ──────────────

@pytest.mark.asyncio
async def test_success_sends_document(db_session, tmp_path, monkeypatch):
    fake, fake_create = _fake_created_file(tmp_path, 1.5)
    monkeypatch.setattr(backup_service, "_create_backup_file", fake_create)
    monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path)
    await set_setting(db_session, "backup_telegram_chat_id", "-100888")
    monkeypatch.setattr(backup_service.settings, "TELEGRAM_BOT_TOKEN", "12345:AA")

    captured: dict = {}

    class _Resp:
        status_code = 200

        def json(self):
            return {"ok": True}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, data=None, files=None):
            captured["url"] = url
            captured["data"] = data
            captured["files"] = files
            return _Resp()

    monkeypatch.setattr(backup_service.httpx, "AsyncClient", _Client)

    result = await run_backup(db_session)

    assert result["status"] == "success"
    assert result["sent_telegram"] is True
    assert result["file_name"] == fake.name
    assert result["size_mb"] == 1.5
    assert "duration_s" in result
    # Gọi Bot API đúng chat_id + caption tiếng Việt
    assert captured["data"]["chat_id"] == "-100888"
    assert "Sao lưu JAMA CRM" in captured["data"]["caption"]
    assert "PostgreSQL" in captured["data"]["caption"]
    assert "12345:AA" in captured["url"]          # token nằm trong URL Bot API
    assert "sendDocument" in captured["url"]
    assert await get_setting(db_session, "backup_last_status") == "success"


# ── (e) pg_dump exit != 0 → status error, detail KHÔNG chứa mật khẩu ─────

@pytest.mark.asyncio
async def test_pg_dump_failure_masks_password(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path)
    monkeypatch.setattr(
        backup_service.settings,
        "DATABASE_URL",
        "postgresql+asyncpg://admin:supersecret@db.internal:5432/jama?ssl=require",
    )

    class _Proc:
        returncode = 1

        async def communicate(self):
            return (
                b"",
                b'pg_dump: error: connection to server failed: '
                b'FATAL: password authentication failed for user "admin"',
            )

    async def _fake_exec(*args, **kwargs):
        return _Proc()

    monkeypatch.setattr(backup_service.asyncio, "create_subprocess_exec", _fake_exec)

    result = await run_backup(db_session)

    assert result["status"] == "error"
    assert "pg_dump" in result["reason"]
    assert "supersecret" not in result["reason"]   # mật khẩu KHÔNG bị lộ
    # (f) last_* được ghi cả khi lỗi tạo file
    assert await get_setting(db_session, "backup_last_status") == "error"
    assert await get_setting(db_session, "backup_last_run_at")
    assert await get_setting(db_session, "backup_last_size_mb") == ""  # chưa có file


# ── (e-bis) pg_dump được gọi với URL libpq đã chuyển đổi ─────────────────

@pytest.mark.asyncio
async def test_pg_dump_invoked_with_libpq_url(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path)
    monkeypatch.setattr(
        backup_service.settings,
        "DATABASE_URL",
        "postgresql+asyncpg://u:p@h:5432/db?ssl=require",
    )
    captured_args: list = []
    captured_kwargs: dict = {}

    class _Proc:
        returncode = 1  # dừng sớm sau khi kiểm tra tham số

        async def communicate(self):
            return (b"", b"boom")

    async def _fake_exec(*args, **kwargs):
        captured_args.extend(args)
        captured_kwargs.update(kwargs)
        return _Proc()

    monkeypatch.setattr(backup_service.asyncio, "create_subprocess_exec", _fake_exec)

    await run_backup(db_session)

    assert captured_args[0] == "pg_dump"
    assert "-Fc" in captured_args
    # URL truyền cho pg_dump đã là libpq (không còn +asyncpg, ssl→sslmode)
    url_arg = captured_args[-1]
    assert url_arg.startswith("postgresql://")
    assert "+asyncpg" not in url_arg
    assert "sslmode=require" in url_arg
    # Mật khẩu KHÔNG nằm trên argv (lộ qua /proc, ps) — chỉ đi qua env PGPASSWORD
    assert ":p@" not in url_arg
    assert all("p" != a and ":p" not in str(a) for a in captured_args[1:-1])
    assert captured_kwargs.get("env", {}).get("PGPASSWORD") == "p"
