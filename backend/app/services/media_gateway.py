"""Storage Gateway ảnh công trình (Đợt 2, 23/10/2026).

Luồng: nhận ảnh → chuẩn hoá JPG (bỏ EXIF, cạnh dài ≤1920) → chống trùng sha256
→ đăng vào nhóm Telegram «JAMA Công trình», mỗi dự án một topic (bot tự tạo)
→ DB chỉ giữ metadata → web/portal xem qua link ký HMAC, backend stream lại từ
Telegram → worker sao thêm một bản sang Drive (`drive_mirror.py`).

Ảnh từ bot không tải về rồi tải lên lại: gửi lại bằng `file_id` (cùng một bot
token với backend) nên nhanh và không tốn băng thông.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.media import MediaFile, ProjectDocument
from app.models.notification import SystemSetting
from app.models.project import Project

logger = logging.getLogger(__name__)

CANH_DAI_TOI_DA = 1920
CHAT_LUONG_JPG = 85
TELEGRAM_TIMEOUT = 60.0
# Link tải file của Telegram sống khoảng 1 giờ.
FILE_PATH_TTL = timedelta(minutes=50)

# Nhóm không bật Topics → nhớ trong RAM để khỏi gọi createForumTopic mỗi ảnh.
_chat_khong_co_topic: set[str] = set()


class MediaError(Exception):
    """Lỗi có thông điệp tiếng Việt đưa thẳng cho người dùng."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Chuẩn hoá ảnh
# ---------------------------------------------------------------------------

def normalize_image(data: bytes) -> tuple[bytes, int, int]:
    """Ảnh bất kỳ Pillow đọc được → JPG q85, cạnh dài ≤1920, đã xoay đúng
    chiều và bỏ EXIF (EXIF của ảnh điện thoại chứa toạ độ GPS nhà khách)."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise MediaError(
            "Không đọc được ảnh. Chỉ nhận JPG/PNG/WebP — ảnh HEIC của iPhone hãy "
            "chụp màn hình hoặc đổi sang JPG rồi gửi lại."
        ) from exc
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        nen = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            nen.paste(img, mask=img.split()[-1])
        else:
            nen.paste(img.convert("RGB"))
        img = nen
    elif img.mode == "L":
        img = img.convert("RGB")
    img.thumbnail((CANH_DAI_TOI_DA, CANH_DAI_TOI_DA))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=CHAT_LUONG_JPG, optimize=True)
    return out.getvalue(), img.width, img.height


# ---------------------------------------------------------------------------
# Link ký HMAC — <img src> không gửi được header Authorization
# ---------------------------------------------------------------------------

def _khoa_ky() -> bytes:
    return (get_settings().JWT_SECRET_KEY or "jama-media-dev").encode()


def ky_media(media_id: str) -> str:
    return hmac.new(_khoa_ky(), media_id.encode(), hashlib.sha256).hexdigest()[:16]


def chu_ky_hop_le(media_id: str, sig: str) -> bool:
    return hmac.compare_digest(ky_media(media_id), sig or "")


def url_media(media: MediaFile | str) -> str:
    """Đường dẫn TƯƠNG ĐỐI so với API base (`/api/v1`). FE tự ghép host —
    backend sau proxy Railway không biết chắc scheme/host công khai."""
    media_id = media if isinstance(media, str) else media.id
    return f"/media/{media_id}/{ky_media(media_id)}.jpg"


def url_avatar(user) -> str | None:
    """URL ảnh đại diện (tương đối /api/v1) hoặc None nếu chưa có ảnh."""
    ver = getattr(user, "avatar_ver", None)
    if not ver:
        return None
    return f"/media/avatar/{user.id}/{ky_media('avatar:' + user.id)}.jpg?v={ver}"


def url_anh_vat_tu(anh_id: str) -> str:
    """URL ảnh mẫu vật tư tải từ máy (tương đối /api/v1)."""
    return f"/media/vat-tu/{anh_id}/{ky_media('vat-tu:' + anh_id)}.jpg"


def lam_anh_mau(data: bytes, canh_dai: int = 800) -> bytes:
    """Ảnh mẫu vật tư: giữ tỉ lệ, cạnh dài ≤`canh_dai`px, JPG q85, xoay đúng, bỏ EXIF."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise MediaError("Không đọc được ảnh. Chỉ nhận JPG/PNG/WebP.") from exc
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        nen = Image.new("RGB", img.size, (255, 255, 255))
        nen.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1]) if img.mode in ("RGBA", "LA", "P") else None
        img = nen if img.mode in ("RGBA", "LA", "P") else img.convert("RGB")
    img.thumbnail((canh_dai, canh_dai), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85, optimize=True)
    return out.getvalue()


def lam_avatar(data: bytes, canh: int = 320) -> bytes:
    """Ảnh bất kỳ → JPG vuông `canh`px (cắt giữa), xoay đúng chiều, bỏ EXIF."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise MediaError("Không đọc được ảnh. Chỉ nhận JPG/PNG/WebP.") from exc
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img = ImageOps.fit(img, (canh, canh), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85, optimize=True)
    return out.getvalue()


# ---------------------------------------------------------------------------
# Telegram Bot API
# ---------------------------------------------------------------------------

async def lay_storage_chat_id(db: AsyncSession) -> str:
    row = await db.get(SystemSetting, "storage_telegram_chat_id")
    return (row.value or "").strip() if row else ""


async def _tg(method: str, data: dict, files: dict | None = None) -> dict:
    if not get_settings().TELEGRAM_BOT_TOKEN:
        raise MediaError("Máy chủ chưa cấu hình TELEGRAM_BOT_TOKEN", 503)
    url = f"https://api.telegram.org/bot{get_settings().TELEGRAM_BOT_TOKEN}/{method}"
    try:
        async with httpx.AsyncClient(timeout=TELEGRAM_TIMEOUT) as client:
            resp = await client.post(url, data=data, files=files)
        body = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise MediaError(f"Không kết nối được Telegram ({type(exc).__name__})", 502) from exc
    if not body.get("ok"):
        raise MediaError(f"Telegram từ chối: {body.get('description', 'không rõ lý do')}", 502)
    kq = body.get("result")
    return kq if kq is not None else {}


async def _dam_bao_topic(db: AsyncSession, project: Project | None, chat_id: str) -> int | None:
    """Topic của dự án trong nhóm kho ảnh; tự tạo lần đầu. Nhóm không bật
    Topics → None (gửi thẳng vào nhóm, caption có #MÃ_DỰ_ÁN)."""
    if project is None or chat_id in _chat_khong_co_topic:
        return None
    if project.telegram_topic_id:
        return project.telegram_topic_id
    try:
        topic = await _tg("createForumTopic", {
            "chat_id": chat_id, "name": f"{project.code} · {project.name}"[:128],
        })
    except MediaError as exc:
        msg = str(exc).lower()
        if "not a forum" in msg or ("forum" in msg and "disabled" in msg):
            _chat_khong_co_topic.add(chat_id)
            return None
        raise
    project.telegram_topic_id = topic.get("message_thread_id")
    await db.flush()
    return project.telegram_topic_id


def _caption(project: Project | None, caption: str | None, nguoi: str | None) -> str:
    phan = []
    if project is not None:
        phan.append("#" + project.code.replace("-", "_"))
    if caption:
        phan.append(caption)
    if nguoi:
        phan.append(f"— {nguoi}")
    return " ".join(phan)[:1000]


async def _gui_vao_topic(db: AsyncSession, project: Project | None, gui) -> tuple[str, object]:
    """Gọi `gui(chat_id, thread_id)` trong topic dự án của nhóm Kho ảnh.
    Topic bị xoá → tạo lại một lần. Trả (chat_id, kết quả)."""
    chat_id = await lay_storage_chat_id(db)
    if not chat_id:
        raise MediaError(
            "Chưa cấu hình nhóm Kho ảnh. Admin vào Cài đặt → Tự động hoá → "
            "«Nhóm Telegram Kho ảnh» để bật lưu ảnh.", 503,
        )
    thread_id = await _dam_bao_topic(db, project, chat_id)
    try:
        kq = await gui(chat_id, thread_id)
    except MediaError as exc:
        # Ai đó xoá topic trong nhóm → tạo lại một lần.
        if thread_id and "thread not found" in str(exc).lower() and project is not None:
            project.telegram_topic_id = None
            kq = await gui(chat_id, await _dam_bao_topic(db, project, chat_id))
        else:
            raise
    return chat_id, kq


async def _dang_anh(
    db: AsyncSession, project: Project | None, photo, caption: str,
) -> tuple[str, dict]:
    """`photo` là bytes JPG hoặc file_id. Trả (chat_id, message)."""

    async def gui(chat_id: str, thread_id: int | None) -> dict:
        data = {"chat_id": chat_id, "caption": caption}
        if thread_id:
            data["message_thread_id"] = str(thread_id)
        if isinstance(photo, bytes):
            return await _tg("sendPhoto", data, files={"photo": ("anh.jpg", photo, "image/jpeg")})
        return await _tg("sendPhoto", {**data, "photo": photo})

    return await _gui_vao_topic(db, project, gui)


async def _dang_album(
    db: AsyncSession, project: Project | None, photos: list[bytes], caption: str,
) -> tuple[str, list[dict]]:
    """Gửi 2–10 ảnh thành MỘT album (sendMediaGroup) — caption nằm ở ảnh đầu
    để Telegram hiện dưới cả album. Trả (chat_id, danh sách message theo thứ tự)."""

    async def gui(chat_id: str, thread_id: int | None) -> list[dict]:
        media = [{"type": "photo", "media": f"attach://p{i}"} for i in range(len(photos))]
        media[0]["caption"] = caption
        data = {"chat_id": chat_id, "media": json.dumps(media, ensure_ascii=False)}
        if thread_id:
            data["message_thread_id"] = str(thread_id)
        files = {f"p{i}": (f"anh{i}.jpg", b, "image/jpeg") for i, b in enumerate(photos)}
        kq = await _tg("sendMediaGroup", data, files=files)
        if not isinstance(kq, list) or len(kq) != len(photos):
            raise MediaError("Telegram trả album không đủ ảnh", 502)
        return kq

    return await _gui_vao_topic(db, project, gui)


def _anh_lon_nhat(msg: dict) -> dict:
    sizes = msg.get("photo") or []
    if not sizes:
        raise MediaError("Telegram không trả về ảnh", 502)
    return sizes[-1]


# ---------------------------------------------------------------------------
# Lưu ảnh
# ---------------------------------------------------------------------------

def _chia_se_mac_dinh(kind: str) -> bool:
    return kind == "tien_do"


async def _ban_cu(db: AsyncSession, khoa: str) -> MediaFile | None:
    return (await db.execute(select(MediaFile).where(MediaFile.sha256 == khoa))).scalar_one_or_none()


async def luu_anh_tu_web(
    db: AsyncSession, *, data: bytes, project: Project | None, user_id: str | None,
    nguoi: str | None, kind: str = "tien_do", caption: str | None = None,
) -> tuple[MediaFile, bool]:
    """Trả (media, deduped)."""
    jpg, w, h = normalize_image(data)
    khoa = hashlib.sha256(jpg).hexdigest()
    cu = await _ban_cu(db, khoa)
    if cu is not None:
        return cu, True
    chat_id, msg = await _dang_anh(db, project, jpg, _caption(project, caption, nguoi))
    lon = _anh_lon_nhat(msg)
    media = MediaFile(
        sha256=khoa, mime="image/jpeg", size_bytes=len(jpg), width=w, height=h,
        project_id=project.id if project else None, uploaded_by=user_id,
        caption=(caption or None) and caption[:300], kind=kind,
        shared_with_customer=_chia_se_mac_dinh(kind),
        telegram_chat_id=chat_id, telegram_message_id=msg.get("message_id"),
        telegram_file_id=lon.get("file_id"),
    )
    db.add(media)
    await db.flush()
    return media, False


ALBUM_TOI_DA = 10  # giới hạn sendMediaGroup của Telegram


async def luu_album_tu_web(
    db: AsyncSession, *, files: list[bytes], project: Project | None, user_id: str | None,
    nguoi: str | None, kind: str = "tien_do", caption: str | None = None,
) -> list[tuple[MediaFile, bool]]:
    """Lưu nhiều ảnh một lượt: ảnh mới gom thành album (mỗi album ≤10 ảnh) để
    nhóm Kho ảnh nhận MỘT tin thay vì N tin. Trả [(media, deduped)] đúng thứ tự gửi lên."""
    chuan: list[tuple[bytes, int, int, str]] = []
    for data in files:
        jpg, w, h = normalize_image(data)
        chuan.append((jpg, w, h, hashlib.sha256(jpg).hexdigest()))

    ket_qua: list[tuple[MediaFile, bool] | None] = [None] * len(chuan)
    moi: list[int] = []  # vị trí ảnh cần đăng
    da_thay: dict[str, int] = {}
    for i, (_, _, _, khoa) in enumerate(chuan):
        cu = await _ban_cu(db, khoa)
        if cu is not None:
            ket_qua[i] = (cu, True)
        elif khoa in da_thay:
            continue  # trùng ngay trong lượt này — điền sau khi ảnh gốc lưu xong
        else:
            da_thay[khoa] = i
            moi.append(i)

    tong = len(moi)
    for dau in range(0, tong, ALBUM_TOI_DA):
        lo = moi[dau:dau + ALBUM_TOI_DA]
        nhan = caption or ""
        if tong > 1:
            dem = f"{tong} ảnh" if tong <= ALBUM_TOI_DA else f"{dau + 1}–{dau + len(lo)}/{tong} ảnh"
            nhan = f"{nhan} ({dem})" if nhan else dem
        cap = _caption(project, nhan, nguoi)
        anh = [chuan[i][0] for i in lo]
        if len(lo) == 1:
            chat_id, msg = await _dang_anh(db, project, anh[0], cap)
            msgs = [msg]
        else:
            chat_id, msgs = await _dang_album(db, project, anh, cap)
        for i, msg in zip(lo, msgs):
            jpg, w, h, khoa = chuan[i]
            lon = _anh_lon_nhat(msg)
            media = MediaFile(
                sha256=khoa, mime="image/jpeg", size_bytes=len(jpg), width=w, height=h,
                project_id=project.id if project else None, uploaded_by=user_id,
                caption=(caption or None) and caption[:300], kind=kind,
                shared_with_customer=_chia_se_mac_dinh(kind),
                telegram_chat_id=chat_id, telegram_message_id=msg.get("message_id"),
                telegram_file_id=lon.get("file_id"),
            )
            db.add(media)
            ket_qua[i] = (media, False)
        await db.flush()

    for i, (_, _, _, khoa) in enumerate(chuan):
        if ket_qua[i] is None:
            ket_qua[i] = (ket_qua[da_thay[khoa]][0], True)
    return ket_qua  # type: ignore[return-value]


async def luu_anh_tu_telegram(
    db: AsyncSession, *, file_id: str, file_unique_id: str, project: Project | None,
    user_id: str | None, nguoi: str | None, kind: str = "tien_do",
    caption: str | None = None, da_o_kho: tuple[str, int] | None = None,
    width: int | None = None, height: int | None = None, size_bytes: int | None = None,
) -> tuple[MediaFile, bool]:
    """Ảnh đã nằm trên Telegram. `da_o_kho=(chat_id, message_id)` khi ảnh được
    thả thẳng vào topic kho — chỉ ghi metadata, không đăng lại."""
    khoa = f"tg:{file_unique_id}"
    cu = await _ban_cu(db, khoa)
    if cu is not None:
        return cu, True
    if da_o_kho is not None:
        chat_id, message_id = da_o_kho
    else:
        chat_id, msg = await _dang_anh(db, project, file_id, _caption(project, caption, nguoi))
        message_id = msg.get("message_id")
        lon = _anh_lon_nhat(msg)
        file_id = lon.get("file_id") or file_id
        width, height, size_bytes = lon.get("width"), lon.get("height"), lon.get("file_size")
    media = MediaFile(
        sha256=khoa, mime="image/jpeg", size_bytes=size_bytes, width=width, height=height,
        project_id=project.id if project else None, uploaded_by=user_id,
        caption=(caption or None) and caption[:300], kind=kind,
        shared_with_customer=_chia_se_mac_dinh(kind),
        telegram_chat_id=str(chat_id), telegram_message_id=message_id,
        telegram_file_id=file_id,
    )
    db.add(media)
    await db.flush()
    return media, False


# ---------------------------------------------------------------------------
# Đọc ảnh
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Tài liệu dự án (PDF/DWG/SKP…) — 23/10/2026
# ---------------------------------------------------------------------------

TAI_LIEU_TOI_DA = 50 * 1024 * 1024   # Bot API sendDocument
TAI_VE_QUA_BOT_TOI_DA = 20 * 1024 * 1024  # Bot API getFile


def ky_tai_lieu(doc_id: str) -> str:
    return ky_media("doc:" + doc_id)


def url_tai_lieu(doc: ProjectDocument) -> str:
    """Tương đối so với `/api/v1` như ảnh; tên file ở cuối để trình duyệt lưu đúng tên."""
    from urllib.parse import quote
    return f"/media/docs/{doc.id}/{ky_tai_lieu(doc.id)}/{quote(doc.filename)}"


def link_tin_nhan(doc: ProjectDocument) -> str | None:
    """t.me/c/<id>/<msg> — chỉ thành viên nhóm mở được (nhóm riêng tư)."""
    chat = (doc.telegram_chat_id or "").lstrip("-")
    if not chat or not doc.telegram_message_id:
        return None
    if chat.startswith("100"):
        chat = chat[3:]
    return f"https://t.me/c/{chat}/{doc.telegram_message_id}"


async def luu_tai_lieu(
    db: AsyncSession, *, data: bytes, filename: str, mime: str | None,
    project: Project, task_id: str | None, tieu_de: str | None,
    user_id: str | None, nguoi: str | None,
) -> ProjectDocument:
    if not data:
        raise MediaError("File rỗng")
    if len(data) > TAI_LIEU_TOI_DA:
        raise MediaError(
            f"File {len(data) // (1024 * 1024)}MB vượt giới hạn 50MB của Telegram. "
            "Nén lại (zip/giảm chất lượng) hoặc dán link Drive vào ô bên cạnh.", 413,
        )
    chat_id = await lay_storage_chat_id(db)
    if not chat_id:
        raise MediaError(
            "Chưa cấu hình nhóm Kho ảnh nên chưa tải file được. Admin vào Cài đặt → "
            "Tự động hoá → «Nhóm Telegram Kho ảnh». Tạm thời dán link vào ô bên cạnh.", 503,
        )
    caption = _caption(project, f"📁 {tieu_de}" if tieu_de else "📁 Tài liệu", nguoi)

    async def gui(thread_id: int | None) -> dict:
        d = {"chat_id": chat_id, "caption": caption}
        if thread_id:
            d["message_thread_id"] = str(thread_id)
        return await _tg("sendDocument", d, files={
            "document": (filename, data, mime or "application/octet-stream"),
        })

    thread_id = await _dam_bao_topic(db, project, chat_id)
    try:
        msg = await gui(thread_id)
    except MediaError as exc:
        if thread_id and "thread not found" in str(exc).lower():
            project.telegram_topic_id = None
            msg = await gui(await _dam_bao_topic(db, project, chat_id))
        else:
            raise
    tep = msg.get("document") or {}
    doc = ProjectDocument(
        project_id=project.id, task_id=task_id, filename=filename[:255], mime=mime,
        size_bytes=len(data), telegram_chat_id=chat_id,
        telegram_message_id=msg.get("message_id"), telegram_file_id=tep.get("file_id"),
        uploaded_by=user_id,
    )
    db.add(doc)
    await db.flush()
    return doc


async def chep_tep_tu_telegram(
    db: AsyncSession, *, from_chat_id: int, message_id: int, thread_id: int | None,
    filename: str, mime: str | None, size_bytes: int | None, file_id: str | None,
    project: Project, tieu_de: str | None, user_id: str | None, nguoi: str | None,
) -> ProjectDocument:
    """Tệp nhân viên gửi bot (/baocao) → chép vào topic dự án của nhóm Kho bằng
    copyMessage (25/10/2026). Không tải về nên tệp nặng mấy cũng chép được
    (bản vẽ .skp 200+ MB) — getFile/sendDocument thì kẹt 20/50 MB.
    Gửi sẵn trong đúng topic dự án → chỉ ghi nhận, không chép lại."""
    chat_id = await lay_storage_chat_id(db)
    if not chat_id:
        raise MediaError(
            "Chưa cấu hình nhóm Kho. Admin vào Cài đặt → Tự động hoá → «Nhóm Telegram Kho ảnh».", 503,
        )
    if str(from_chat_id) == chat_id and thread_id and thread_id == project.telegram_topic_id:
        msg_id = message_id
    else:
        caption = _caption(project, f"📁 {tieu_de}" if tieu_de else f"📁 {filename}", nguoi)

        async def gui(cid: str, tid: int | None) -> dict:
            d = {"chat_id": cid, "from_chat_id": str(from_chat_id), "message_id": str(message_id),
                 "caption": caption}
            if tid:
                d["message_thread_id"] = str(tid)
            return await _tg("copyMessage", d)

        _, kq = await _gui_vao_topic(db, project, gui)
        msg_id = kq.get("message_id")
    doc = ProjectDocument(
        project_id=project.id, filename=filename[:255], mime=(mime or None) and mime[:100],
        size_bytes=size_bytes or 0, telegram_chat_id=chat_id, telegram_message_id=msg_id,
        telegram_file_id=file_id, uploaded_by=user_id,
    )
    db.add(doc)
    await db.flush()
    return doc


async def tai_tai_lieu(doc: ProjectDocument) -> bytes:
    if not doc.telegram_file_id:
        raise MediaError("File không còn trên Telegram", 404)
    info = await _tg("getFile", {"file_id": doc.telegram_file_id})
    url = f"https://api.telegram.org/file/bot{get_settings().TELEGRAM_BOT_TOKEN}/{info.get('file_path')}"
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.get(url)
    except httpx.HTTPError as exc:
        raise MediaError("Không tải được file từ Telegram", 502) from exc
    if resp.status_code != 200:
        raise MediaError("Không tải được file từ Telegram", 502)
    return resp.content


async def tai_anh(db: AsyncSession, media: MediaFile) -> bytes:
    """Bytes ảnh từ Telegram (cache `file_path` 50 phút)."""
    if not media.telegram_file_id:
        raise MediaError("Ảnh không còn trên Telegram", 404)
    if (
        not media.telegram_file_path_cached
        or not media.cached_at
        or _now() - media.cached_at > FILE_PATH_TTL
    ):
        info = await _tg("getFile", {"file_id": media.telegram_file_id})
        media.telegram_file_path_cached = info.get("file_path")
        media.cached_at = _now()
        await db.flush()
    url = f"https://api.telegram.org/file/bot{get_settings().TELEGRAM_BOT_TOKEN}/{media.telegram_file_path_cached}"
    try:
        async with httpx.AsyncClient(timeout=TELEGRAM_TIMEOUT) as client:
            resp = await client.get(url)
    except httpx.HTTPError as exc:
        raise MediaError("Không tải được ảnh từ Telegram", 502) from exc
    if resp.status_code != 200:
        # file_path hết hạn sớm hơn dự kiến → bỏ cache để lần sau lấy lại.
        media.telegram_file_path_cached = None
        await db.flush()
        raise MediaError("Không tải được ảnh từ Telegram", 502)
    return resp.content


async def gui_anh_thu(db: AsyncSession) -> dict:
    """Nút «Thử gửi 1 ảnh» ở Cài đặt — ảnh 64×64 vào nhóm kho, không theo dự án."""
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (64, 64), (196, 154, 108)).save(out, format="JPEG")
    chat_id, msg = await _dang_anh(db, None, out.getvalue(), "✅ JAMA ERP: thử kết nối Kho ảnh")
    return {"chat_id": chat_id, "message_id": msg.get("message_id")}
