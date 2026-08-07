"""Tests Backup — cấu hình, kẹp retention, dọn file local, RBAC, hợp đồng API mới.

Logic run_backup (pg_dump / Telegram) nằm ở test_backup_service.py.
"""

import time
import zipfile

import pytest
from httpx import AsyncClient

from app.services import backup_service
from app.services.backup_service import (
    MAX_RETENTION_DAYS,
    _cleanup_local,
    _snapshot_sqlite_to_zip,
    get_backup_settings,
    list_local_backups,
    set_setting,
)
from tests.conftest import auth_header


# ── Cấu hình (service) ───────────────────────────────────────────────────

@pytest.mark.asyncio
class TestBackupSettings:
    async def test_defaults(self, db_session):
        cfg = await get_backup_settings(db_session)
        assert cfg["backup_enabled"] == "true"
        assert cfg["backup_hour"] == "5"
        assert cfg["backup_retention_days"] == "180"
        assert cfg["backup_telegram_chat_id"] == ""

    async def test_retention_clamped_to_max(self, db_session):
        await set_setting(db_session, "backup_retention_days", "9999")
        cfg = await get_backup_settings(db_session)
        assert cfg["backup_retention_days"] == str(MAX_RETENTION_DAYS)

    async def test_retention_clamped_to_min(self, db_session):
        await set_setting(db_session, "backup_retention_days", "0")
        cfg = await get_backup_settings(db_session)
        assert cfg["backup_retention_days"] == "1"

    async def test_invalid_retention_falls_back(self, db_session):
        await set_setting(db_session, "backup_retention_days", "abc")
        cfg = await get_backup_settings(db_session)
        assert cfg["backup_retention_days"] == str(MAX_RETENTION_DAYS)

    async def test_hour_clamped(self, db_session):
        await set_setting(db_session, "backup_hour", "99")
        cfg = await get_backup_settings(db_session)
        assert cfg["backup_hour"] == "23"


# ── Snapshot & dọn file (filesystem, thư mục tạm) ────────────────────────

class TestSnapshotAndCleanup:
    def test_snapshot_creates_valid_zip(self, tmp_path):
        import sqlite3

        src = tmp_path / "test.db"
        conn = sqlite3.connect(str(src))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        conn.close()

        out = tmp_path / "jama_backup_test.zip"
        _snapshot_sqlite_to_zip(src, out)

        assert out.exists()
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
            assert "jama.db" in names
            assert "metadata.json" in names
        assert not out.with_suffix(".tmp.db").exists()

    def test_cleanup_deletes_old_zip_and_dump(self, tmp_path, monkeypatch):
        import os

        monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path)

        old_zip = tmp_path / "jama_backup_old.zip"
        old_dump = tmp_path / "jama-crm-old.dump"      # dọn cả file pg_dump
        new_zip = tmp_path / "jama_backup_new.zip"
        other = tmp_path / "keep-me.txt"
        for f in (old_zip, old_dump, new_zip, other):
            f.write_bytes(b"data")

        old_time = time.time() - 200 * 86400
        os.utime(old_zip, (old_time, old_time))
        os.utime(old_dump, (old_time, old_time))

        deleted = _cleanup_local(retention_days=180)
        assert deleted == 2
        assert not old_zip.exists()
        assert not old_dump.exists()
        assert new_zip.exists()
        assert other.exists()  # file không phải backup — giữ nguyên

    def test_list_local_backups(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path)
        (tmp_path / "jama_backup_a.zip").write_bytes(b"aaa")
        (tmp_path / "jama-crm-b.dump").write_bytes(b"bbbbb")

        items = list_local_backups()
        assert len(items) == 2
        assert all("name" in i and "size_bytes" in i for i in items)


# ── API: RBAC + hợp đồng settings/run ────────────────────────────────────

@pytest.mark.asyncio
class TestBackupAPI:
    async def test_settings_admin_ok(self, client: AsyncClient, admin_user):
        resp = await client.get("/api/v1/backup/settings", headers=auth_header(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled"] is True
        assert body["hour"] == 5
        assert body["retention_days"] == 180
        assert body["telegram_chat_id"] == ""
        assert body["telegram_configured"] is False   # chưa có chat_id
        assert body["last_status"] == "never"
        assert body["last_run_at"] is None
        assert body["last_size_mb"] is None

    async def test_settings_blocks_non_admin(self, client: AsyncClient, sales_user, accountant_user):
        for user in (sales_user, accountant_user):
            resp = await client.get("/api/v1/backup/settings", headers=auth_header(user))
            assert resp.status_code == 403

    async def test_update_settings(self, client: AsyncClient, admin_user):
        resp = await client.put(
            "/api/v1/backup/settings",
            json={
                "enabled": False,
                "hour": 4,
                "retention_days": 90,
                "telegram_chat_id": "-1001234567890",
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled"] is False
        assert body["hour"] == 4
        assert body["retention_days"] == 90
        assert body["telegram_chat_id"] == "-1001234567890"

    async def test_update_chat_id_can_be_cleared(self, client: AsyncClient, admin_user):
        await client.put(
            "/api/v1/backup/settings",
            json={"telegram_chat_id": "-100999"},
            headers=auth_header(admin_user),
        )
        resp = await client.put(
            "/api/v1/backup/settings",
            json={"telegram_chat_id": ""},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["telegram_chat_id"] == ""

    async def test_update_rejects_retention_over_max(self, client: AsyncClient, admin_user):
        resp = await client.put(
            "/api/v1/backup/settings",
            json={"retention_days": 181},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 400

    async def test_update_rejects_bad_hour(self, client: AsyncClient, admin_user):
        resp = await client.put(
            "/api/v1/backup/settings",
            json={"hour": 25},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 400

    async def test_gdrive_endpoints_removed(self, client: AsyncClient, admin_user):
        # Các endpoint Google Drive đã bị gỡ hoàn toàn → 404/405
        resp = await client.get(
            "/api/v1/backup/gdrive/auth-url", headers=auth_header(admin_user)
        )
        assert resp.status_code in (404, 405)

    async def test_run_backup_no_telegram_returns_error(
        self, client: AsyncClient, admin_user, tmp_path, monkeypatch
    ):
        """Chưa cấu hình chat_id → status error THẬT (không phải 'skipped' giả)."""
        import sqlite3

        src = tmp_path / "jama.db"
        conn = sqlite3.connect(str(src))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path / "backups")
        monkeypatch.setattr(backup_service, "_sqlite_db_path", lambda: src)
        monkeypatch.setattr(
            backup_service.settings, "DATABASE_URL", "sqlite+aiosqlite:///./jama.db"
        )

        resp = await client.post("/api/v1/backup/run", headers=auth_header(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "error"
        assert "Telegram" in body["reason"]
        # File backup vẫn được tạo local dù chưa gửi được
        files = list((tmp_path / "backups").glob("jama_backup_*.zip"))
        assert len(files) == 1

    async def test_run_backup_blocks_non_admin(self, client: AsyncClient, sales_user):
        resp = await client.post("/api/v1/backup/run", headers=auth_header(sales_user))
        assert resp.status_code == 403
