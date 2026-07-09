"""Backup Service — sao lưu database hàng ngày (local + Google Drive OAuth).

Tính năng (cấu hình bởi admin trong Settings):
- Bật/tắt sao lưu tự động lúc 5h sáng (giờ VN, chỉnh được)
- Giữ tối đa 180 ngày backup (local + Drive đều tự dọn bản cũ)
- Snapshot SQLite an toàn bằng sqlite3 backup API (không hỏng file khi đang ghi)
- Upload Google Drive qua OAuth 2.0 (authorization code flow, lưu refresh_token)

Ghi chú: bản Docker dùng PostgreSQL — backup tự động chỉ hỗ trợ SQLite;
PostgreSQL dùng pg_dump theo hướng dẫn IT.
"""

import asyncio
import json
import logging
import os
import secrets
import sqlite3
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.notification import SystemSetting

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Constants & settings keys
# ---------------------------------------------------------------------------

BACKUP_DIR = Path(__file__).resolve().parent.parent.parent / "backups"  # backend/backups/
MAX_RETENTION_DAYS = 180

DEFAULT_BACKUP_SETTINGS: dict[str, str] = {
    "backup_enabled": "true",
    "backup_hour": "5",                 # 5h sáng VN
    "backup_retention_days": "180",     # tối đa 180
    "backup_gdrive_enabled": "false",   # bật sau khi kết nối OAuth
}

# Keys lưu riêng (không hiển thị trực tiếp): gdrive_client_id, gdrive_client_secret,
# gdrive_refresh_token, gdrive_folder_id, gdrive_oauth_state, gdrive_account_email,
# backup_last_run, backup_last_status

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GDRIVE_API = "https://www.googleapis.com/drive/v3"
GDRIVE_UPLOAD_API = "https://www.googleapis.com/upload/drive/v3/files"
GDRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
GDRIVE_FOLDER_NAME = "JAMA-CRM-Backups"


# ---------------------------------------------------------------------------
# Settings helpers (dùng chung bảng system_settings)
# ---------------------------------------------------------------------------

async def get_setting(db: AsyncSession, key: str, default: str = "") -> str:
    row = await db.get(SystemSetting, key)
    return row.value if row and row.value else default


async def set_setting(db: AsyncSession, key: str, value: str) -> None:
    row = await db.get(SystemSetting, key)
    if row:
        row.value = value
    else:
        db.add(SystemSetting(key=key, value=value))
    await db.flush()


async def get_backup_settings(db: AsyncSession) -> dict[str, str]:
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key.in_(list(DEFAULT_BACKUP_SETTINGS.keys())))
    )
    stored = {s.key: s.value for s in result.scalars().all() if s.value}
    merged = {**DEFAULT_BACKUP_SETTINGS, **stored}
    # Clamp retention về tối đa 180 ngày
    try:
        merged["backup_retention_days"] = str(
            max(1, min(MAX_RETENTION_DAYS, int(merged["backup_retention_days"])))
        )
    except (TypeError, ValueError):
        merged["backup_retention_days"] = str(MAX_RETENTION_DAYS)
    return merged


# ---------------------------------------------------------------------------
# 1. Local backup — SQLite snapshot → zip
# ---------------------------------------------------------------------------

def _sqlite_db_path() -> Path | None:
    """Resolve SQLite file path from DATABASE_URL, or None when not SQLite."""
    url = settings.DATABASE_URL
    if "sqlite" not in url:
        return None
    # sqlite+aiosqlite:///./jama.db  → ./jama.db (relative to backend/)
    raw = url.split("///")[-1]
    p = Path(raw)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent.parent.parent / raw.lstrip("./")
    return p


def _snapshot_sqlite_to_zip(db_path: Path, out_zip: Path) -> None:
    """Consistent SQLite snapshot (sqlite3 backup API) → zip file. Blocking."""
    tmp_db = out_zip.with_suffix(".tmp.db")
    src = sqlite3.connect(str(db_path))
    try:
        dst = sqlite3.connect(str(tmp_db))
        try:
            src.backup(dst)  # an toàn kể cả khi app đang ghi
        finally:
            dst.close()
    finally:
        src.close()

    try:
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(tmp_db, arcname="jama.db")
            zf.writestr(
                "metadata.json",
                json.dumps(
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "app": settings.APP_NAME,
                        "source": str(db_path.name),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
    finally:
        tmp_db.unlink(missing_ok=True)


def _cleanup_local(retention_days: int) -> int:
    """Delete local backups older than retention. Returns number deleted."""
    if not BACKUP_DIR.exists():
        return 0
    cutoff = time.time() - retention_days * 86400
    deleted = 0
    for f in BACKUP_DIR.glob("jama_backup_*.zip"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                deleted += 1
        except OSError as exc:
            logger.warning("Cannot delete old backup %s: %s", f, exc)
    return deleted


def list_local_backups() -> list[dict]:
    """List local backup files (newest first)."""
    if not BACKUP_DIR.exists():
        return []
    items = []
    for f in sorted(BACKUP_DIR.glob("jama_backup_*.zip"), reverse=True):
        st = f.stat()
        items.append(
            {
                "name": f.name,
                "size_bytes": st.st_size,
                "created_at": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
            }
        )
    return items


# ---------------------------------------------------------------------------
# 2. Google Drive OAuth helpers
# ---------------------------------------------------------------------------

def _redirect_uri() -> str:
    return f"{settings.API_BASE_URL.rstrip('/')}/api/v1/backup/gdrive/callback"


async def build_gdrive_auth_url(db: AsyncSession) -> str:
    """Build Google consent URL. Requires client_id/secret already saved."""
    client_id = await get_setting(db, "gdrive_client_id")
    if not client_id:
        raise ValueError("Chưa cấu hình Google OAuth Client ID")

    state = secrets.token_urlsafe(24)
    await set_setting(db, "gdrive_oauth_state", state)

    params = {
        "client_id": client_id,
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": GDRIVE_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def handle_gdrive_callback(db: AsyncSession, code: str, state: str) -> dict:
    """Exchange authorization code → refresh token, store it."""
    saved_state = await get_setting(db, "gdrive_oauth_state")
    if not saved_state or state != saved_state:
        raise ValueError("OAuth state không khớp — thử kết nối lại")
    await set_setting(db, "gdrive_oauth_state", "")

    client_id = await get_setting(db, "gdrive_client_id")
    client_secret = await get_setting(db, "gdrive_client_secret")

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": _redirect_uri(),
                "grant_type": "authorization_code",
            },
        )
        if resp.status_code != 200:
            raise ValueError(f"Đổi token thất bại: {resp.text[:200]}")
        tokens = resp.json()

    refresh_token = tokens.get("refresh_token", "")
    if not refresh_token:
        raise ValueError("Google không trả refresh_token — hãy Revoke quyền cũ rồi kết nối lại")

    await set_setting(db, "gdrive_refresh_token", refresh_token)
    await set_setting(db, "backup_gdrive_enabled", "true")

    # Lấy email tài khoản (hiển thị cho admin biết đang kết nối acc nào)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            about = await client.get(
                f"{GDRIVE_API}/about",
                params={"fields": "user(emailAddress)"},
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            email = about.json().get("user", {}).get("emailAddress", "")
            if email:
                await set_setting(db, "gdrive_account_email", email)
    except Exception:
        pass

    return {"status": "connected"}


async def _gdrive_access_token(db: AsyncSession) -> str | None:
    """Refresh token → short-lived access token."""
    refresh_token = await get_setting(db, "gdrive_refresh_token")
    client_id = await get_setting(db, "gdrive_client_id")
    client_secret = await get_setting(db, "gdrive_client_secret")
    if not (refresh_token and client_id and client_secret):
        return None
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                },
            )
            if resp.status_code == 200:
                return resp.json().get("access_token")
            logger.warning("GDrive token refresh failed: %s", resp.text[:200])
    except Exception as exc:
        logger.warning("GDrive token refresh error: %s", exc)
    return None


async def _gdrive_ensure_folder(db: AsyncSession, token: str) -> str | None:
    """Get or create the backup folder on Drive, cache folder_id."""
    folder_id = await get_setting(db, "gdrive_folder_id")
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        if folder_id:
            check = await client.get(f"{GDRIVE_API}/files/{folder_id}", headers=headers, params={"fields": "id,trashed"})
            if check.status_code == 200 and not check.json().get("trashed"):
                return folder_id
        resp = await client.post(
            f"{GDRIVE_API}/files",
            headers=headers,
            json={"name": GDRIVE_FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"},
        )
        if resp.status_code == 200:
            folder_id = resp.json()["id"]
            await set_setting(db, "gdrive_folder_id", folder_id)
            return folder_id
    logger.warning("Cannot ensure GDrive folder")
    return None


async def _gdrive_upload(db: AsyncSession, file_path: Path) -> bool:
    """Upload one backup file to Drive (multipart)."""
    token = await _gdrive_access_token(db)
    if not token:
        return False
    folder_id = await _gdrive_ensure_folder(db, token)
    if not folder_id:
        return False

    metadata = json.dumps({"name": file_path.name, "parents": [folder_id]})
    files = {
        "metadata": ("metadata", metadata, "application/json; charset=UTF-8"),
        "file": (file_path.name, file_path.read_bytes(), "application/zip"),
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                GDRIVE_UPLOAD_API,
                params={"uploadType": "multipart", "fields": "id"},
                headers={"Authorization": f"Bearer {token}"},
                files=files,
            )
            if resp.status_code == 200:
                return True
            logger.warning("GDrive upload failed: %s", resp.text[:200])
    except Exception as exc:
        logger.warning("GDrive upload error: %s", exc)
    return False


async def _gdrive_cleanup(db: AsyncSession, retention_days: int) -> int:
    """Delete Drive backups older than retention. Returns number deleted."""
    token = await _gdrive_access_token(db)
    if not token:
        return 0
    folder_id = await get_setting(db, "gdrive_folder_id")
    if not folder_id:
        return 0

    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).strftime("%Y-%m-%dT%H:%M:%S")
    deleted = 0
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{GDRIVE_API}/files",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "q": f"'{folder_id}' in parents and createdTime < '{cutoff}' and trashed = false",
                    "fields": "files(id,name)",
                    "pageSize": 100,
                },
            )
            for f in resp.json().get("files", []):
                d = await client.delete(
                    f"{GDRIVE_API}/files/{f['id']}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                if d.status_code in (200, 204):
                    deleted += 1
    except Exception as exc:
        logger.warning("GDrive cleanup error: %s", exc)
    return deleted


# ---------------------------------------------------------------------------
# 3. Main entry — run full backup
# ---------------------------------------------------------------------------

async def run_backup(db: AsyncSession) -> dict:
    """Create local backup, upload to Drive (if connected), apply retention."""
    cfg = await get_backup_settings(db)
    retention = int(cfg["backup_retention_days"])

    db_path = _sqlite_db_path()
    if db_path is None:
        result = {"status": "skipped", "reason": "DATABASE_URL không phải SQLite — dùng pg_dump cho PostgreSQL"}
        await set_setting(db, "backup_last_status", json.dumps(result, ensure_ascii=False))
        return result
    if not db_path.exists():
        result = {"status": "failed", "reason": f"Không tìm thấy file database: {db_path.name}"}
        await set_setting(db, "backup_last_status", json.dumps(result, ensure_ascii=False))
        return result

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    out_zip = BACKUP_DIR / f"jama_backup_{stamp}.zip"

    # Snapshot (blocking sqlite ops trong thread riêng)
    await asyncio.to_thread(_snapshot_sqlite_to_zip, db_path, out_zip)
    size_mb = round(out_zip.stat().st_size / (1024 * 1024), 2)

    # Google Drive upload
    gdrive_uploaded = False
    if cfg.get("backup_gdrive_enabled") == "true":
        gdrive_uploaded = await _gdrive_upload(db, out_zip)

    # Retention cleanup
    local_deleted = await asyncio.to_thread(_cleanup_local, retention)
    gdrive_deleted = 0
    if cfg.get("backup_gdrive_enabled") == "true":
        gdrive_deleted = await _gdrive_cleanup(db, retention)

    result = {
        "status": "completed",
        "file": out_zip.name,
        "size_mb": size_mb,
        "gdrive_uploaded": gdrive_uploaded,
        "local_deleted": local_deleted,
        "gdrive_deleted": gdrive_deleted,
        "retention_days": retention,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    await set_setting(db, "backup_last_run", result["at"])
    await set_setting(db, "backup_last_status", json.dumps(result, ensure_ascii=False))
    await db.commit()
    logger.info("Backup completed: %s (%.2f MB, gdrive=%s)", out_zip.name, size_mb, gdrive_uploaded)
    return result
