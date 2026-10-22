"""Sao ảnh công trình sang Google Drive công ty (Đợt 2, 23/10/2026).

Bản gốc ảnh nằm ở nhóm Telegram kho ảnh; Drive là bản sao thứ hai để công ty
không phụ thuộc một nơi. Chạy trong worker mỗi 5 phút, mỗi lượt ≤20 ảnh.

Khoá đặt ở biến môi trường `GDRIVE_SA_JSON` (không lưu DB):
- key Service Account (`"type": "service_account"`) — thư mục gốc phải nằm
  trong Shared Drive (Google Workspace) hoặc được share Editor cho email SA.
  Lưu ý: Google không cấp dung lượng riêng cho Service Account, nên tải vào
  thư mục «Drive của tôi» của tài khoản Gmail thường sẽ bị từ chối
  `storageQuotaExceeded` — khi đó dùng dạng dưới.
- hoặc thông tin OAuth của tài khoản công ty (`"type": "authorized_user"`,
  có `client_id`, `client_secret`, `refresh_token`) — ảnh tính vào dung lượng
  tài khoản đó.

Không kéo thư viện Google: ký JWT bằng python-jose (đã có), gọi REST bằng httpx.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.media import MediaFile
from app.models.project import Project

logger = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
FILES_URL = "https://www.googleapis.com/drive/v3/files"
UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
SCOPE = "https://www.googleapis.com/auth/drive"
MOI_LUOT = 20

_token_cache: dict[str, float | str] = {}


class DriveError(Exception):
    pass


def da_cau_hinh() -> bool:
    return bool(get_settings().GDRIVE_SA_JSON.strip() and get_settings().GDRIVE_MEDIA_FOLDER_ID.strip())


def _khoa() -> dict:
    try:
        return json.loads(get_settings().GDRIVE_SA_JSON)
    except (TypeError, ValueError) as exc:
        raise DriveError("GDRIVE_SA_JSON không phải JSON hợp lệ") from exc


async def _access_token(client: httpx.AsyncClient) -> str:
    if _token_cache.get("token") and float(_token_cache.get("exp", 0)) > time.time() + 60:
        return str(_token_cache["token"])
    k = _khoa()
    if k.get("type") == "authorized_user" or k.get("refresh_token"):
        data = {
            "grant_type": "refresh_token",
            "client_id": k.get("client_id", ""),
            "client_secret": k.get("client_secret", ""),
            "refresh_token": k.get("refresh_token", ""),
        }
    else:
        from jose import jwt

        now = int(time.time())
        assertion = jwt.encode(
            {
                "iss": k.get("client_email"), "scope": SCOPE, "aud": TOKEN_URL,
                "iat": now, "exp": now + 3600,
            },
            k.get("private_key", ""),
            algorithm="RS256",
        )
        data = {"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}
    resp = await client.post(TOKEN_URL, data=data)
    if resp.status_code != 200:
        raise DriveError(f"Google từ chối khoá ({resp.status_code}): {resp.text[:200]}")
    body = resp.json()
    _token_cache["token"] = body["access_token"]
    _token_cache["exp"] = time.time() + int(body.get("expires_in", 3600))
    return body["access_token"]


async def _thu_muc_du_an(client: httpx.AsyncClient, token: str, db: AsyncSession, project: Project | None) -> str:
    goc = get_settings().GDRIVE_MEDIA_FOLDER_ID.strip()
    if project is None:
        return goc
    if project.drive_folder_id:
        return project.drive_folder_id
    resp = await client.post(
        FILES_URL,
        params={"supportsAllDrives": "true", "fields": "id"},
        headers={"Authorization": f"Bearer {token}"},
        json={"name": project.code, "mimeType": "application/vnd.google-apps.folder", "parents": [goc]},
    )
    if resp.status_code not in (200, 201):
        raise DriveError(f"Không tạo được thư mục {project.code} ({resp.status_code}): {resp.text[:200]}")
    project.drive_folder_id = resp.json()["id"]
    await db.flush()
    return project.drive_folder_id


async def _tai_len(client: httpx.AsyncClient, token: str, folder_id: str, ten: str, data: bytes) -> str:
    ranh_gioi = "jama_media_boundary"
    meta = json.dumps({"name": ten, "parents": [folder_id]}).encode()
    body = (
        f"--{ranh_gioi}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
        + meta
        + f"\r\n--{ranh_gioi}\r\nContent-Type: image/jpeg\r\n\r\n".encode()
        + data
        + f"\r\n--{ranh_gioi}--".encode()
    )
    resp = await client.post(
        UPLOAD_URL,
        params={"uploadType": "multipart", "supportsAllDrives": "true", "fields": "id"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/related; boundary={ranh_gioi}",
        },
        content=body,
    )
    if resp.status_code not in (200, 201):
        raise DriveError(f"Drive từ chối tệp ({resp.status_code}): {resp.text[:300]}")
    return resp.json()["id"]


async def sao_anh_cho(db: AsyncSession) -> dict:
    """Một lượt sao ảnh. Chưa cấu hình → không đụng gì, ảnh giữ `pending` để
    khi admin đặt khoá thì ảnh cũ cũng được sao."""
    if not da_cau_hinh():
        return {"status": "skipped", "reason": "Chưa đặt GDRIVE_SA_JSON / GDRIVE_MEDIA_FOLDER_ID"}
    from app.services.media_gateway import MediaError, tai_anh

    rows = (await db.execute(
        select(MediaFile).where(MediaFile.mirror_status == "pending")
        .order_by(MediaFile.created_at).limit(MOI_LUOT)
    )).scalars().all()
    done = errors = 0
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            token = await _access_token(client)
        except DriveError as exc:
            logger.warning("Drive mirror: %s", exc)
            return {"status": "error", "error": str(exc)}
        for media in rows:
            try:
                project = await db.get(Project, media.project_id) if media.project_id else None
                folder = await _thu_muc_du_an(client, token, db, project)
                data = await tai_anh(db, media)
                ngay = (media.created_at or datetime.now()).strftime("%Y%m%d")
                media.drive_file_id = await _tai_len(client, token, folder, f"{ngay}_{media.id}.jpg", data)
                media.mirror_status = "done"
                media.mirror_error = None
                done += 1
            except (DriveError, MediaError, httpx.HTTPError) as exc:
                media.mirror_status = "error"
                media.mirror_error = str(exc)[:500]
                errors += 1
            await db.flush()
    await db.commit()
    return {"status": "completed", "done": done, "errors": errors}


async def trang_thai(db: AsyncSession) -> dict:
    dem = dict((await db.execute(
        select(MediaFile.mirror_status, func.count()).group_by(MediaFile.mirror_status)
    )).all())
    loi_gan_nhat = (await db.execute(
        select(MediaFile.mirror_error).where(MediaFile.mirror_status == "error")
        .order_by(MediaFile.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    return {
        "drive_configured": da_cau_hinh(),
        "total": sum(dem.values()),
        "pending": dem.get("pending", 0),
        "done": dem.get("done", 0),
        "error": dem.get("error", 0),
        "last_error": loi_gan_nhat,
    }
