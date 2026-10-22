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
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.media import MediaFile
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
    return body.get("result") or {}


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


async def _dang_anh(
    db: AsyncSession, project: Project | None, photo, caption: str,
) -> tuple[str, dict]:
    """`photo` là bytes JPG hoặc file_id. Trả (chat_id, message)."""
    chat_id = await lay_storage_chat_id(db)
    if not chat_id:
        raise MediaError(
            "Chưa cấu hình nhóm Kho ảnh. Admin vào Cài đặt → Tự động hoá → "
            "«Nhóm Telegram Kho ảnh» để bật lưu ảnh.", 503,
        )

    async def gui(thread_id: int | None) -> dict:
        data = {"chat_id": chat_id, "caption": caption}
        if thread_id:
            data["message_thread_id"] = str(thread_id)
        if isinstance(photo, bytes):
            return await _tg("sendPhoto", data, files={"photo": ("anh.jpg", photo, "image/jpeg")})
        return await _tg("sendPhoto", {**data, "photo": photo})

    thread_id = await _dam_bao_topic(db, project, chat_id)
    try:
        msg = await gui(thread_id)
    except MediaError as exc:
        # Ai đó xoá topic trong nhóm → tạo lại một lần.
        if thread_id and "thread not found" in str(exc).lower() and project is not None:
            project.telegram_topic_id = None
            msg = await gui(await _dam_bao_topic(db, project, chat_id))
        else:
            raise
    return chat_id, msg


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
    chat_id, msg = await _dang_anh(db, None, out.getvalue(), "✅ JAMA CRM: thử kết nối Kho ảnh")
    return {"chat_id": chat_id, "message_id": msg.get("message_id")}
