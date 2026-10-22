"""Kho ảnh công trình — upload, xem, chia sẻ cho khách (Đợt 2, 23/10/2026)."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.permissions import quyen_hieu_luc
from app.middleware.rbac import la_pic_du_an
from app.models.media import MEDIA_KINDS, MediaFile
from app.models.project import Project
from app.models.user import User
from app.services import drive_mirror
from app.services.media_gateway import (
    MediaError,
    chu_ky_hop_le,
    gui_anh_thu,
    lay_storage_chat_id,
    luu_anh_tu_telegram,
    luu_anh_tu_web,
    tai_anh,
    url_media,
)

router = APIRouter(prefix="/media", tags=["media"])

TOI_DA_BYTES = 10 * 1024 * 1024
_ADMIN = ("admin", "executive")


def _loi(exc: MediaError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def _kiem_kind(kind: str) -> str:
    if kind not in MEDIA_KINDS:
        raise HTTPException(status_code=400, detail=f"Loại ảnh không hợp lệ: {kind}")
    return kind


async def _tim_du_an(db: AsyncSession, project_id: str | None, project_code: str | None) -> Project:
    if project_id:
        project = await db.get(Project, project_id)
    elif project_code:
        project = (await db.execute(
            select(Project).where(Project.code == project_code.strip().upper())
        )).scalar_one_or_none()
    else:
        raise HTTPException(status_code=400, detail="Thiếu dự án")
    if project is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")
    return project


async def _kiem_xem_du_an(db: AsyncSession, user: User, project: Project) -> None:
    # Cùng luật với trang chi tiết dự án — tránh nhân viên liệt kê ảnh nhà khách
    # của dự án ngoài phạm vi.
    from app.api.projects import require_project_access

    await require_project_access(project.id, user, db)


def _ra_dict(m: MediaFile, user_name: str | None = None) -> dict:
    return {
        "id": m.id,
        "url": url_media(m),
        "width": m.width,
        "height": m.height,
        "caption": m.caption,
        "kind": m.kind,
        "shared_with_customer": m.shared_with_customer,
        "project_id": m.project_id,
        "uploaded_by": m.uploaded_by,
        "user_name": user_name,
        "mirror_status": m.mirror_status,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


# ── Upload từ web ──────────────────────────────────────────────────────────

@router.post("/upload", status_code=201)
async def upload_media(
    file: UploadFile = File(...),
    project_id: str | None = Form(default=None),
    project_code: str | None = Form(default=None),
    kind: str = Form(default="tien_do"),
    caption: str | None = Form(default=None, max_length=300),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _kiem_kind(kind)
    project = await _tim_du_an(db, project_id, project_code)
    await _kiem_xem_du_an(db, current_user, project)
    data = await file.read(TOI_DA_BYTES + 1)
    if len(data) > TOI_DA_BYTES:
        raise HTTPException(status_code=413, detail="Ảnh tối đa 10 MB")
    if not data:
        raise HTTPException(status_code=400, detail="Tệp rỗng")
    try:
        media, deduped = await luu_anh_tu_web(
            db, data=data, project=project, user_id=current_user.id,
            nguoi=current_user.full_name, kind=kind, caption=caption,
        )
    except MediaError as exc:
        raise _loi(exc)
    await db.commit()
    return {**_ra_dict(media, current_user.full_name), "deduped": deduped}


# ── Ảnh từ bot Telegram ────────────────────────────────────────────────────

class TelegramPhoto(BaseModel):
    file_id: str = Field(..., max_length=255)
    file_unique_id: str = Field(..., max_length=100)
    project_code: str | None = None
    project_id: str | None = None
    kind: str = "tien_do"
    caption: str | None = Field(default=None, max_length=300)


@router.post("/from-telegram", status_code=201)
async def media_from_telegram(
    data: TelegramPhoto,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ảnh nhân viên gửi bot trong /baocao, /suco → đăng lại vào topic dự án
    bằng file_id (không tải về). Không gác phạm vi — giống các lệnh hiện
    trường khác của bot: thợ/giám sát ít khi là PIC dự án."""
    _kiem_kind(data.kind)
    project = await _tim_du_an(db, data.project_id, data.project_code)
    try:
        media, deduped = await luu_anh_tu_telegram(
            db, file_id=data.file_id, file_unique_id=data.file_unique_id, project=project,
            user_id=current_user.id, nguoi=current_user.full_name, kind=data.kind,
            caption=data.caption,
        )
    except MediaError as exc:
        raise _loi(exc)
    await db.commit()
    return {**_ra_dict(media, current_user.full_name), "deduped": deduped}


class TelegramIngest(BaseModel):
    file_id: str = Field(..., max_length=255)
    file_unique_id: str = Field(..., max_length=100)
    chat_id: int
    message_id: int
    thread_id: int
    caption: str | None = Field(default=None, max_length=1000)
    width: int | None = None
    height: int | None = None
    file_size: int | None = None


@router.post("/ingest-telegram", status_code=201)
async def ingest_telegram(
    data: TelegramIngest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Nhân viên thả ảnh thẳng vào topic dự án trong nhóm kho → chỉ ghi
    metadata (ảnh đã nằm đúng chỗ, không đăng lại)."""
    kho = await lay_storage_chat_id(db)
    if not kho or str(data.chat_id) != kho:
        raise HTTPException(status_code=404, detail="Không phải nhóm Kho ảnh")
    project = (await db.execute(
        select(Project).where(Project.telegram_topic_id == data.thread_id)
    )).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Topic này chưa gắn dự án nào")
    media, deduped = await luu_anh_tu_telegram(
        db, file_id=data.file_id, file_unique_id=data.file_unique_id, project=project,
        user_id=current_user.id, nguoi=current_user.full_name, kind="tien_do",
        caption=(data.caption or None) and data.caption[:300],
        da_o_kho=(str(data.chat_id), data.message_id),
        width=data.width, height=data.height, size_bytes=data.file_size,
    )
    await db.commit()
    return {**_ra_dict(media, current_user.full_name), "deduped": deduped,
            "project_code": project.code}


# ── Cài đặt (admin) ────────────────────────────────────────────────────────

def _admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in _ADMIN:
        raise HTTPException(status_code=403, detail="Chỉ Ban Giám Đốc")
    return current_user


@router.get("/status")
async def media_status(db: AsyncSession = Depends(get_db), _: User = Depends(_admin)):
    return {
        "storage_chat_configured": bool(await lay_storage_chat_id(db)),
        **await drive_mirror.trang_thai(db),
    }


@router.post("/test")
async def media_test(db: AsyncSession = Depends(get_db), _: User = Depends(_admin)):
    try:
        return await gui_anh_thu(db)
    except MediaError as exc:
        raise _loi(exc)


@router.post("/mirror/retry")
async def media_mirror_retry(db: AsyncSession = Depends(get_db), _: User = Depends(_admin)):
    res = await db.execute(
        update(MediaFile).where(MediaFile.mirror_status == "error")
        .values(mirror_status="pending", mirror_error=None)
    )
    await db.commit()
    return {"requeued": res.rowcount or 0}


# ── Danh sách & chia sẻ ────────────────────────────────────────────────────

@router.get("")
async def list_media(
    project_id: str = Query(...),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=60, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _tim_du_an(db, project_id, None)
    await _kiem_xem_du_an(db, current_user, project)
    total = await db.scalar(
        select(func.count()).select_from(MediaFile).where(MediaFile.project_id == project.id)
    )
    rows = (await db.execute(
        select(MediaFile, User.full_name)
        .outerjoin(User, MediaFile.uploaded_by == User.id)
        .where(MediaFile.project_id == project.id)
        .order_by(MediaFile.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).all()
    return {"items": [_ra_dict(m, ten) for m, ten in rows], "total": total or 0, "page": page}


class MediaPatch(BaseModel):
    shared_with_customer: bool | None = None
    caption: str | None = Field(default=None, max_length=300)


@router.patch("/{media_id}")
async def patch_media(
    media_id: str,
    data: MediaPatch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    media = await db.get(MediaFile, media_id)
    if media is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh")
    project = await db.get(Project, media.project_id) if media.project_id else None
    duoc = (
        current_user.role in _ADMIN
        or media.uploaded_by == current_user.id
        or (project is not None and la_pic_du_an(current_user, project))
        or (await quyen_hieu_luc(current_user, db)).get("canEditTasks")
    )
    if not duoc:
        raise HTTPException(
            status_code=403,
            detail="Chỉ người đăng ảnh, PIC dự án hoặc người có quyền «Sửa Công việc» được đổi",
        )
    if data.shared_with_customer is not None:
        media.shared_with_customer = data.shared_with_customer
    if data.caption is not None:
        media.caption = data.caption.strip() or None
    await db.commit()
    return _ra_dict(media)


# ── Xem ảnh (link ký, không cần đăng nhập) ─────────────────────────────────

@router.get("/{media_id}/{sig}.jpg")
async def get_media_file(media_id: str, sig: str, db: AsyncSession = Depends(get_db)):
    if not chu_ky_hop_le(media_id, sig):
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh")
    media = await db.get(MediaFile, media_id)
    if media is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh")
    try:
        data = await tai_anh(db, media)
    except MediaError as exc:
        await db.commit()
        raise _loi(exc)
    await db.commit()  # lưu cache file_path
    return Response(
        content=data,
        media_type=media.mime or "image/jpeg",
        headers={"Cache-Control": "private, max-age=86400", "ETag": f'"{media.id}"'},
    )
