"""Backup Service — sao lưu database hàng ngày và gửi bản sao qua Telegram.

Tính năng (cấu hình bởi admin trong Cài đặt):
- Bật/tắt sao lưu tự động lúc 5h sáng (giờ VN, chỉnh được)
- Giữ tối đa 180 ngày backup local (tự dọn bản cũ)
- PostgreSQL (production): dump bằng pg_dump định dạng custom (-Fc, đã nén)
- SQLite (dev): snapshot an toàn bằng sqlite3 backup API rồi nén zip
- Đẩy file backup ra nhóm Telegram (offsite duy nhất) qua Bot API sendDocument

Quyết định dự án: bản sao lưu offsite chỉ dùng Telegram. Google Drive đã gỡ bỏ.
"""

import asyncio
import json
import logging
import os
import re
import sqlite3
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.notification import SystemSetting

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Hằng số & khóa cấu hình
# ---------------------------------------------------------------------------

BACKUP_DIR = Path(__file__).resolve().parent.parent.parent / "backups"  # backend/backups/
MAX_RETENTION_DAYS = 180
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

_MB = 1024 * 1024
# Bot API sendDocument giới hạn 50 MB — chừa biên an toàn còn 49 MB.
MAX_TELEGRAM_MB = 49
TELEGRAM_TIMEOUT = 120.0  # giây

# Khóa lưu trong bảng system_settings (KISS key-value)
DEFAULT_BACKUP_SETTINGS: dict[str, str] = {
    "backup_enabled": "true",
    "backup_hour": "5",                  # 5h sáng VN
    "backup_retention_days": "180",      # tối đa 180 ngày
    "backup_telegram_chat_id": "",       # chat_id nhóm Telegram nhận backup
}
# Khóa kết quả lần chạy gần nhất (ghi cả khi lỗi):
#   backup_last_run_at   — ISO giờ VN của lần chạy gần nhất
#   backup_last_status   — "success" | "error" | (chưa có → "never")
#   backup_last_detail   — mô tả tiếng Việt (thành công hoặc lý do lỗi)
#   backup_last_size_mb  — dung lượng file (MB) hoặc rỗng


# ---------------------------------------------------------------------------
# Helper cấu hình (dùng chung bảng system_settings)
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
    """Trả về cấu hình sao lưu (dạng chuỗi, theo khóa system_settings).

    Worker và API cùng đọc hàm này; giá trị được kẹp về khoảng hợp lệ để
    đảm bảo an toàn kể cả khi DB chứa giá trị lỗi.
    """
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key.in_(list(DEFAULT_BACKUP_SETTINGS.keys())))
    )
    stored = {s.key: s.value for s in result.scalars().all() if s.value is not None}
    merged = {**DEFAULT_BACKUP_SETTINGS, **stored}

    # Kẹp retention về 1..180 ngày
    try:
        merged["backup_retention_days"] = str(
            max(1, min(MAX_RETENTION_DAYS, int(merged["backup_retention_days"])))
        )
    except (TypeError, ValueError):
        merged["backup_retention_days"] = str(MAX_RETENTION_DAYS)

    # Kẹp hour về 0..23
    try:
        merged["backup_hour"] = str(max(0, min(23, int(merged["backup_hour"]))))
    except (TypeError, ValueError):
        merged["backup_hour"] = "5"

    return merged


def has_telegram_token() -> bool:
    """TELEGRAM_BOT_TOKEN đã được cấu hình trên máy chủ hay chưa."""
    return bool(settings.TELEGRAM_BOT_TOKEN)


# ---------------------------------------------------------------------------
# Chuyển đổi URL PostgreSQL: SQLAlchemy/asyncpg → libpq (pg_dump)
# ---------------------------------------------------------------------------

# asyncpg dùng ?ssl=<mode>; libpq (pg_dump) dùng ?sslmode=<mode>.
# Một số giá trị boolean của asyncpg cần ánh xạ sang tên sslmode của libpq.
_SSL_VALUE_MAP = {
    "true": "require",
    "1": "require",
    "on": "require",
    "false": "disable",
    "0": "disable",
    "off": "disable",
}


def _is_postgres() -> bool:
    return "postgres" in settings.DATABASE_URL


def _pg_libpq_url(async_url: str) -> str:
    """Chuyển 'postgresql+asyncpg://...?ssl=require' → 'postgresql://...?sslmode=require'.

    - Bỏ phần '+asyncpg' (hoặc driver bất kỳ) khỏi scheme, chuẩn hóa 'postgres' → 'postgresql'.
    - Đổi query param 'ssl' (asyncpg) sang 'sslmode' (libpq); ánh xạ true/false → require/disable.
    - Giữ nguyên phần userinfo (user:pass@host) để không phá mật khẩu đã mã hóa sẵn.
    """
    if "://" in async_url:
        scheme, rest = async_url.split("://", 1)
    else:
        scheme, rest = "postgresql", async_url

    scheme = scheme.split("+", 1)[0]  # postgresql+asyncpg → postgresql
    if scheme == "postgres":
        scheme = "postgresql"

    if "?" in rest:
        base, query = rest.split("?", 1)
    else:
        base, query = rest, ""

    if query:
        out_pairs: list[tuple[str, str]] = []
        for key, value in parse_qsl(query, keep_blank_values=True):
            if key == "ssl":
                out_pairs.append(("sslmode", _SSL_VALUE_MAP.get(value.lower(), value)))
            elif key == "sslmode":
                out_pairs.append(("sslmode", value))
            else:
                out_pairs.append((key, value))
        query = urlencode(out_pairs)

    url = f"{scheme}://{base}"
    if query:
        url = f"{url}?{query}"
    return url


def _password_from_url(url: str) -> str:
    """Trích mật khẩu trong userinfo (user:pass@) để lọc khỏi log lỗi. '' nếu không có."""
    m = re.search(r"://[^:/@]+:([^@]+)@", url)
    return m.group(1) if m else ""


def _mask_url(url: str) -> str:
    """Che mật khẩu trong URL: postgresql://user:secret@host → postgresql://user:***@host."""
    return re.sub(r"(://[^:/@]+:)[^@]*(@)", r"\1***\2", url)


def _strip_password_from_url(url: str) -> str:
    """Bỏ HẲN mật khẩu khỏi URL (user@host) — URL này được phép nằm trên argv."""
    return re.sub(r"(://[^:/@]+):[^@]*(@)", r"\1\2", url)


def _clean_pg_error(stderr: bytes | str, raw_url: str) -> str:
    """Rút gọn stderr của pg_dump, ĐẢM BẢO không để lộ mật khẩu DB."""
    text = stderr.decode("utf-8", errors="replace") if isinstance(stderr, bytes) else str(stderr)
    text = " ".join(text.split()).strip()
    # Che mật khẩu nếu lỡ xuất hiện trong stderr hoặc URL bị echo ra.
    pwd = _password_from_url(raw_url)
    if pwd:
        text = text.replace(pwd, "***")
    text = text.replace(raw_url, _mask_url(raw_url))
    if not text:
        return "không có thông tin chi tiết"
    return text[:300]


# ---------------------------------------------------------------------------
# Tạo file backup (PostgreSQL: pg_dump · SQLite: snapshot zip)
# ---------------------------------------------------------------------------

class BackupError(Exception):
    """Lỗi nghiệp vụ khi tạo/gửi backup — thông điệp tiếng Việt cho admin."""


def _sqlite_db_path() -> Path | None:
    """Đường dẫn file SQLite từ DATABASE_URL, hoặc None nếu không phải SQLite."""
    url = settings.DATABASE_URL
    if "sqlite" not in url:
        return None
    # sqlite+aiosqlite:///./jama.db → ./jama.db (tương đối so với backend/)
    raw = url.split("///")[-1]
    p = Path(raw)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent.parent.parent / raw.lstrip("./")
    return p


def _snapshot_sqlite_to_zip(db_path: Path, out_zip: Path) -> None:
    """Snapshot SQLite nhất quán (sqlite3 backup API) → file zip. Blocking."""
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


async def _pg_dump_to_file(out_file: Path) -> None:
    """Chạy pg_dump định dạng custom (-Fc, đã nén) ra out_file.

    Raise BackupError (không lộ mật khẩu) nếu pg_dump thất bại.
    """
    libpq_url = _pg_libpq_url(settings.DATABASE_URL)
    # Mật khẩu KHÔNG được nằm trên argv (lộ qua /proc/<pid>/cmdline, ps trong container)
    # → truyền qua env PGPASSWORD; URL trên argv đã bỏ hẳn mật khẩu.
    password = unquote(_password_from_url(libpq_url))
    env = {**os.environ, "PGPASSWORD": password} if password else None
    proc = await asyncio.create_subprocess_exec(
        "pg_dump",
        "-Fc",
        "--no-owner",
        "--no-privileges",
        "-f",
        str(out_file),
        _strip_password_from_url(libpq_url),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        out_file.unlink(missing_ok=True)
        detail = _clean_pg_error(stderr, settings.DATABASE_URL)
        raise BackupError(f"pg_dump lỗi (mã {proc.returncode}): {detail}")


async def _create_backup_file(now_vn: datetime) -> tuple[Path, str, float]:
    """Tạo file backup. Trả về (đường_dẫn, loại_db, dung_lượng_MB).

    Loại DB: "PostgreSQL" hoặc "SQLite". Raise BackupError nếu không tạo được.
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now_vn.strftime("%Y%m%d-%H%M%S")

    if _is_postgres():
        out_file = BACKUP_DIR / f"jama-crm-{stamp}.dump"
        await _pg_dump_to_file(out_file)
        db_kind = "PostgreSQL"
    else:
        db_path = _sqlite_db_path()
        if db_path is None or not db_path.exists():
            raise BackupError(
                f"Không tìm thấy file database SQLite: {db_path.name if db_path else '(không rõ)'}"
            )
        out_file = BACKUP_DIR / f"jama_backup_{stamp}.zip"
        # sqlite ops blocking → chạy trong thread riêng
        await asyncio.to_thread(_snapshot_sqlite_to_zip, db_path, out_file)
        db_kind = "SQLite"

    size_mb = round(out_file.stat().st_size / _MB, 2)
    return out_file, db_kind, size_mb


# ---------------------------------------------------------------------------
# Gửi file qua Telegram Bot API
# ---------------------------------------------------------------------------

async def _telegram_send_document(chat_id: str, file_path: Path, caption: str) -> None:
    """Gửi file backup tới nhóm Telegram qua sendDocument (multipart).

    Raise BackupError nếu Bot API trả lỗi.
    """
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendDocument"
    data = {"chat_id": chat_id, "caption": caption}
    async with httpx.AsyncClient(timeout=TELEGRAM_TIMEOUT) as client:
        with file_path.open("rb") as fh:
            files = {"document": (file_path.name, fh, "application/octet-stream")}
            resp = await client.post(url, data=data, files=files)

    if resp.status_code != 200:
        raise BackupError(f"Telegram trả HTTP {resp.status_code}")
    try:
        body = resp.json()
    except ValueError:
        raise BackupError("Telegram trả phản hồi không hợp lệ")
    if not body.get("ok"):
        raise BackupError(f"Telegram từ chối tệp: {body.get('description', 'không rõ lý do')}")


# ---------------------------------------------------------------------------
# Dọn file local quá hạn & liệt kê backup
# ---------------------------------------------------------------------------

_BACKUP_GLOBS = ("jama_backup_*.zip", "jama-crm-*.dump")


def _cleanup_local(retention_days: int) -> int:
    """Xóa các file backup local cũ hơn retention. Trả về số file đã xóa."""
    if not BACKUP_DIR.exists():
        return 0
    cutoff = time.time() - retention_days * 86400
    deleted = 0
    for pattern in _BACKUP_GLOBS:
        for f in BACKUP_DIR.glob(pattern):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    deleted += 1
            except OSError as exc:
                logger.warning("Không xóa được backup cũ %s: %s", f, exc)
    return deleted


def list_local_backups() -> list[dict]:
    """Liệt kê file backup local (mới nhất trước)."""
    if not BACKUP_DIR.exists():
        return []
    items: list[dict] = []
    for pattern in _BACKUP_GLOBS:
        for f in BACKUP_DIR.glob(pattern):
            st = f.stat()
            items.append(
                {
                    "name": f.name,
                    "size_bytes": st.st_size,
                    "created_at": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                }
            )
    items.sort(key=lambda i: i["created_at"], reverse=True)
    return items


# ---------------------------------------------------------------------------
# Ghi kết quả lần chạy gần nhất
# ---------------------------------------------------------------------------

async def _write_last(
    db: AsyncSession,
    now_vn: datetime,
    status: str,
    detail: str,
    size_mb: float | None,
) -> None:
    """Ghi backup_last_* vào system_settings (gọi cả khi thành công lẫn lỗi)."""
    await set_setting(db, "backup_last_run_at", now_vn.isoformat())
    await set_setting(db, "backup_last_status", status)
    await set_setting(db, "backup_last_detail", detail)
    await set_setting(db, "backup_last_size_mb", "" if size_mb is None else str(size_mb))


async def _finish_error(
    db: AsyncSession,
    now_vn: datetime,
    reason: str,
    *,
    size_mb: float | None = None,
) -> dict:
    """Ghi trạng thái lỗi rồi trả về payload chuẩn theo hợp đồng API."""
    await _write_last(db, now_vn, "error", reason, size_mb)
    await db.commit()
    logger.warning("Sao lưu lỗi: %s", reason)
    return {"status": "error", "reason": reason}


# ---------------------------------------------------------------------------
# Entry point — chạy toàn bộ quy trình sao lưu
# ---------------------------------------------------------------------------

async def run_backup(db: AsyncSession) -> dict:
    """Tạo file backup, gửi qua Telegram, dọn bản cũ theo retention.

    Trả về (theo hợp đồng API):
      - Thành công: {status, size_mb, duration_s, file_name, sent_telegram: True}
      - Lỗi:        {status: "error", reason: "<tiếng Việt>"}
    Kết quả luôn được ghi vào backup_last_* (kể cả khi lỗi).
    """
    cfg = await get_backup_settings(db)
    retention = int(cfg["backup_retention_days"])
    chat_id = (cfg.get("backup_telegram_chat_id") or "").strip()
    now_vn = datetime.now(VN_TZ)
    started = time.monotonic()

    # 1) Tạo file backup (pg_dump hoặc snapshot SQLite)
    try:
        file_path, db_kind, size_mb = await _create_backup_file(now_vn)
    except BackupError as exc:
        return await _finish_error(db, now_vn, str(exc))
    except Exception as exc:  # lỗi ngoài dự kiến — không để crash worker
        logger.exception("Lỗi bất ngờ khi tạo file backup")
        return await _finish_error(db, now_vn, f"Lỗi tạo file backup: {exc}")

    # 2) Dọn bản cũ theo retention (file mới vừa tạo luôn được giữ)
    await asyncio.to_thread(_cleanup_local, retention)

    # 3) Kiểm tra điều kiện gửi Telegram
    if not chat_id:
        return await _finish_error(
            db,
            now_vn,
            "Chưa cấu hình nhóm Telegram nhận backup — vào Cài đặt dán Chat ID",
            size_mb=size_mb,
        )
    if not has_telegram_token():
        return await _finish_error(
            db,
            now_vn,
            "Máy chủ chưa cấu hình TELEGRAM_BOT_TOKEN — liên hệ IT để bổ sung",
            size_mb=size_mb,
        )
    if size_mb > MAX_TELEGRAM_MB:
        return await _finish_error(
            db,
            now_vn,
            f"File backup {size_mb} MB vượt giới hạn {MAX_TELEGRAM_MB} MB của Telegram — "
            "hãy giảm số ngày giữ bản sao (retention) hoặc liên hệ IT để sao lưu thủ công. "
            "File vẫn được lưu trên máy chủ.",
            size_mb=size_mb,
        )

    # 4) Gửi file qua Telegram
    caption = (
        f"🗄 Sao lưu JAMA CRM · {now_vn.strftime('%d/%m/%Y %H:%M')} · "
        f"{db_kind} · {size_mb} MB"
    )
    try:
        await _telegram_send_document(chat_id, file_path, caption)
    except BackupError as exc:
        return await _finish_error(db, now_vn, str(exc), size_mb=size_mb)
    except Exception as exc:
        logger.exception("Lỗi bất ngờ khi gửi Telegram")
        # Che token bot nếu lỡ xuất hiện trong thông điệp ngoại lệ (URL Bot API chứa token)
        msg = str(exc)
        if settings.TELEGRAM_BOT_TOKEN:
            msg = msg.replace(settings.TELEGRAM_BOT_TOKEN, "***")
        return await _finish_error(
            db, now_vn, f"Gửi Telegram thất bại: {type(exc).__name__}: {msg[:200]}", size_mb=size_mb
        )

    # 5) Thành công
    duration_s = round(time.monotonic() - started, 2)
    detail = f"Đã gửi {file_path.name} ({size_mb} MB) tới Telegram"
    await _write_last(db, now_vn, "success", detail, size_mb)
    await db.commit()
    logger.info("Sao lưu thành công: %s (%.2f MB, %s)", file_path.name, size_mb, db_kind)
    return {
        "status": "success",
        "size_mb": size_mb,
        "duration_s": duration_s,
        "file_name": file_path.name,
        "sent_telegram": True,
    }
