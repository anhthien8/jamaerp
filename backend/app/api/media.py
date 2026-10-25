"""Kho ảnh công trình — upload, xem, chia sẻ cho khách (Đợt 2, 23/10/2026)."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.permissions import quyen_hieu_luc
from app.middleware.rbac import la_pic_du_an
from app.models.media import MEDIA_KINDS, MediaFile, ProjectDocument
from app.models.project import Project, Task
from app.models.user import User, UserAvatar
from app.services import drive_mirror
from app.services.media_gateway import (
    MediaError,
    chu_ky_hop_le,
    chep_tep_tu_telegram,
    gui_anh_thu,
    lay_storage_chat_id,
    luu_anh_tu_telegram,
    luu_album_tu_web,
    luu_anh_tu_web,
    TAI_VE_QUA_BOT_TOI_DA,
    link_tin_nhan,
    luu_tai_lieu,
    tai_anh,
    tai_tai_lieu,
    url_media,
    url_tai_lieu,
)

router = APIRouter(prefix="/media", tags=["media"])

TOI_DA_BYTES = 10 * 1024 * 1024
TOI_DA_ANH_MOT_LUOT = 30
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


@router.post("/upload-batch", status_code=201)
async def upload_media_batch(
    files: list[UploadFile] = File(...),
    project_id: str | None = Form(default=None),
    project_code: str | None = Form(default=None),
    kind: str = Form(default="tien_do"),
    caption: str | None = Form(default=None, max_length=300),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Nhiều ảnh một lượt → nhóm Kho ảnh nhận thành album (1 tin / ≤10 ảnh)."""
    _kiem_kind(kind)
    if not files:
        raise HTTPException(status_code=400, detail="Chưa chọn ảnh")
    if len(files) > TOI_DA_ANH_MOT_LUOT:
        raise HTTPException(status_code=400, detail=f"Tối đa {TOI_DA_ANH_MOT_LUOT} ảnh mỗi lượt")
    project = await _tim_du_an(db, project_id, project_code)
    await _kiem_xem_du_an(db, current_user, project)
    datas: list[bytes] = []
    for f in files:
        data = await f.read(TOI_DA_BYTES + 1)
        if len(data) > TOI_DA_BYTES:
            raise HTTPException(status_code=413, detail=f"{f.filename or 'Ảnh'}: tối đa 10 MB")
        if not data:
            raise HTTPException(status_code=400, detail="Tệp rỗng")
        datas.append(data)
    try:
        ket_qua = await luu_album_tu_web(
            db, files=datas, project=project, user_id=current_user.id,
            nguoi=current_user.full_name, kind=kind, caption=caption,
        )
    except MediaError as exc:
        raise _loi(exc)
    await db.commit()
    return {
        "items": [{**_ra_dict(m, current_user.full_name), "deduped": d} for m, d in ket_qua],
        "deduped_count": sum(1 for _, d in ket_qua if d),
    }


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

# ── Tài liệu dự án: tải thẳng từ CRM thay vì tự gửi Telegram rồi dán link (23/10) ──

@router.post("/task-file", status_code=201)
async def upload_task_file(
    file: UploadFile = File(...),
    task_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tải file kết quả giai đoạn của đầu việc. Ghi luôn vào final_file_url + lịch sử phiên bản."""
    from app.api.projects import _kiem_quyen_sua_task
    from app.schemas.project import TaskResponse

    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Đầu việc không tồn tại")
    await _kiem_quyen_sua_task(db, current_user, task, phan_cong=False)
    project = await db.get(Project, task.project_id)
    data = await file.read()
    try:
        doc = await luu_tai_lieu(
            db, data=data, filename=file.filename or "tai-lieu", mime=file.content_type,
            project=project, task_id=task.id, tieu_de=task.title,
            user_id=current_user.id, nguoi=current_user.full_name,
        )
    except MediaError as exc:
        await db.commit()  # giữ topic vừa tạo nếu có
        raise _loi(exc)
    url = url_tai_lieu(doc)
    task.final_file_url = url
    versions = list(task.final_file_versions or [])
    versions.append({
        "url": url, "version": len(versions) + 1, "label": doc.filename,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    })
    task.final_file_versions = versions
    await db.flush()
    return TaskResponse.model_validate(task)


@router.get("/docs/{doc_id}/{sig}/{ten}")
async def get_task_file(doc_id: str, sig: str, ten: str, db: AsyncSession = Depends(get_db)):
    """Link ký HMAC như ảnh (mở tab mới không gửi được JWT). >20MB → link tin nhắn Telegram."""
    if not chu_ky_hop_le("doc:" + doc_id, sig):
        raise HTTPException(status_code=404, detail="Không tìm thấy file")
    doc = await db.get(ProjectDocument, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy file")
    if doc.size_bytes > TAI_VE_QUA_BOT_TOI_DA:
        link = link_tin_nhan(doc)
        if not link:
            raise HTTPException(status_code=404, detail="Không tìm thấy file")
        return RedirectResponse(link, status_code=302)
    try:
        data = await tai_tai_lieu(doc)
    except MediaError as exc:
        raise _loi(exc)
    la_pdf_anh = (doc.mime or "").startswith(("application/pdf", "image/"))
    return Response(
        content=data,
        media_type=doc.mime or "application/octet-stream",
        headers={
            "Content-Disposition": f"{'inline' if la_pdf_anh else 'attachment'}; filename*=UTF-8''{quote(doc.filename)}",
            "Cache-Control": "private, max-age=86400",
        },
    )


@router.get("/avatar/{user_id}/{sig}.jpg")
async def get_avatar(user_id: str, sig: str, db: AsyncSession = Depends(get_db)):
    """Ảnh đại diện — URL ký HMAC (thẻ <img> không gửi được JWT). URL có ?v=
    đổi mỗi lần thay ảnh nên cho cache lâu."""
    if not chu_ky_hop_le("avatar:" + user_id, sig):
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh")
    av = await db.get(UserAvatar, user_id)
    if av is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh")
    return Response(
        content=av.data,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=2592000"},
    )


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


class TelegramDocument(BaseModel):
    """Tệp nhân viên gửi bot trong /baocao (bản vẽ, PDF, video…)."""
    project_code: str | None = Field(default=None, max_length=50)
    project_id: str | None = None
    from_chat_id: int
    message_id: int
    thread_id: int | None = None
    file_id: str | None = Field(default=None, max_length=255)
    file_name: str = Field(..., min_length=1, max_length=255)
    mime: str | None = Field(default=None, max_length=100)
    file_size: int | None = None
    caption: str | None = Field(default=None, max_length=300)


@router.post("/document-from-telegram", status_code=201)
async def document_from_telegram(
    data: TelegramDocument,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Chép tệp vào topic dự án trong nhóm Kho (copyMessage, không giới hạn
    dung lượng) + ghi vào Tài liệu dự án. Trả link t.me tới bản trong topic."""
    project = await _tim_du_an(db, data.project_id, data.project_code)
    try:
        doc = await chep_tep_tu_telegram(
            db, from_chat_id=data.from_chat_id, message_id=data.message_id,
            thread_id=data.thread_id, filename=data.file_name, mime=data.mime,
            size_bytes=data.file_size, file_id=data.file_id, project=project,
            tieu_de=data.caption, user_id=current_user.id, nguoi=current_user.full_name,
        )
    except MediaError as exc:
        raise _loi(exc)
    await db.commit()
    return {
        "id": doc.id, "filename": doc.filename, "size_bytes": doc.size_bytes,
        "link": link_tin_nhan(doc), "url": url_tai_lieu(doc),
    }
