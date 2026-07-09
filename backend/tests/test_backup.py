"""Tests for Backup — settings, retention clamp, local cleanup, RBAC, run flow."""

import time
import zipfile
from pathlib import Path

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


# ── Settings ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestBackupSettings:
    async def test_defaults(self, db_session):
        cfg = await get_backup_settings(db_session)
        assert cfg["backup_enabled"] == "true"
        assert cfg["backup_hour"] == "5"
        assert cfg["backup_retention_days"] == "180"

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


# ── Snapshot & cleanup (filesystem, temp dir) ────────────────────────────

class TestSnapshotAndCleanup:
    def test_snapshot_creates_valid_zip(self, tmp_path):
        # Create a tiny sqlite db
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
        # Temp db must be cleaned up
        assert not out.with_suffix(".tmp.db").exists()

    def test_cleanup_deletes_only_old_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path)

        old = tmp_path / "jama_backup_old.zip"
        new = tmp_path / "jama_backup_new.zip"
        other = tmp_path / "keep-me.txt"
        for f in (old, new, other):
            f.write_bytes(b"data")

        # Make `old` look 200 days old
        old_time = time.time() - 200 * 86400
        import os
        os.utime(old, (old_time, old_time))

        deleted = _cleanup_local(retention_days=180)
        assert deleted == 1
        assert not old.exists()
        assert new.exists()
        assert other.exists()  # non-backup files untouched

    def test_list_local_backups(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path)
        (tmp_path / "jama_backup_a.zip").write_bytes(b"aaa")
        (tmp_path / "jama_backup_b.zip").write_bytes(b"bbbbb")

        items = list_local_backups()
        assert len(items) == 2
        assert all("name" in i and "size_bytes" in i for i in items)


# ── API RBAC & validation ────────────────────────────────────────────────

@pytest.mark.asyncio
class TestBackupAPI:
    async def test_settings_admin_ok(self, client: AsyncClient, admin_user):
        resp = await client.get("/api/v1/backup/settings", headers=auth_header(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["backup_hour"] == "5"
        assert body["max_retention_days"] == MAX_RETENTION_DAYS
        assert body["gdrive_connected"] is False

    async def test_settings_blocks_non_admin(self, client: AsyncClient, sales_user, accountant_user):
        for user in (sales_user, accountant_user):
            resp = await client.get("/api/v1/backup/settings", headers=auth_header(user))
            assert resp.status_code == 403

    async def test_update_settings(self, client: AsyncClient, admin_user):
        resp = await client.put(
            "/api/v1/backup/settings",
            json={"backup_enabled": False, "backup_hour": 4, "backup_retention_days": 90},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["backup_enabled"] == "false"
        assert body["backup_hour"] == "4"
        assert body["backup_retention_days"] == "90"

    async def test_update_rejects_retention_over_max(self, client: AsyncClient, admin_user):
        resp = await client.put(
            "/api/v1/backup/settings",
            json={"backup_retention_days": 181},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 400

    async def test_update_rejects_bad_hour(self, client: AsyncClient, admin_user):
        resp = await client.put(
            "/api/v1/backup/settings",
            json={"backup_hour": 25},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 400

    async def test_auth_url_requires_client_id(self, client: AsyncClient, admin_user):
        resp = await client.get("/api/v1/backup/gdrive/auth-url", headers=auth_header(admin_user))
        assert resp.status_code == 400  # chưa cấu hình client id

    async def test_auth_url_after_client_configured(self, client: AsyncClient, admin_user):
        await client.put(
            "/api/v1/backup/settings",
            json={"gdrive_client_id": "test-client-id.apps.googleusercontent.com", "gdrive_client_secret": "sec"},
            headers=auth_header(admin_user),
        )
        resp = await client.get("/api/v1/backup/gdrive/auth-url", headers=auth_header(admin_user))
        assert resp.status_code == 200
        url = resp.json()["auth_url"]
        assert "accounts.google.com" in url
        assert "test-client-id" in url
        assert "drive.file" in url

    async def test_callback_rejects_bad_state(self, client: AsyncClient):
        # Callback không cần JWT nhưng state sai → redirect error
        resp = await client.get(
            "/api/v1/backup/gdrive/callback",
            params={"code": "x", "state": "wrong-state"},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 307)
        assert "gdrive=error" in resp.headers["location"]

    async def test_disconnect(self, client: AsyncClient, admin_user):
        resp = await client.post("/api/v1/backup/gdrive/disconnect", headers=auth_header(admin_user))
        assert resp.status_code == 200
        settings_resp = await client.get("/api/v1/backup/settings", headers=auth_header(admin_user))
        assert settings_resp.json()["gdrive_connected"] is False

    async def test_run_backup_via_api(self, client: AsyncClient, admin_user, tmp_path, monkeypatch):
        # Point backup dir + db path to temp files
        import sqlite3

        src = tmp_path / "jama.db"
        conn = sqlite3.connect(str(src))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path / "backups")
        monkeypatch.setattr(backup_service, "_sqlite_db_path", lambda: src)

        resp = await client.post("/api/v1/backup/run", headers=auth_header(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["file"].startswith("jama_backup_")
        assert body["gdrive_uploaded"] is False  # chưa kết nối Drive
        assert (tmp_path / "backups" / body["file"]).exists()

    async def test_run_backup_blocks_non_admin(self, client: AsyncClient, sales_user):
        resp = await client.post("/api/v1/backup/run", headers=auth_header(sales_user))
        assert resp.status_code == 403
