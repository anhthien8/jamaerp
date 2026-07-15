"""Chạy Alembic migration lúc khởi động app (trước create_all).

Chống failure mode "boot code mới trên DB cũ": nếu app khởi động trước khi
migrate, create_all sẽ tạo bảng mới nhưng KHÔNG thêm cột vào bảng cũ →
lần migrate sau đụng 'table already exists'. Gọi run_migrations() trong
lifespan (trước create_all) loại bỏ hoàn toàn tình huống này.

Logic stamp/upgrade giống scripts/db_upgrade.py:
- DB mới tinh              -> upgrade head (tạo full schema)
- DB cũ chưa có alembic    -> stamp baseline rồi upgrade head
- DB đã quản lý            -> upgrade head
"""

import logging
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

logger = logging.getLogger(__name__)

BASELINE_REV = "ac9de03e7289"

# backend/ — nơi chứa alembic.ini và thư mục alembic/
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


async def _detect_state(database_url: str, is_sqlite: bool) -> str:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            if is_sqlite:
                q = "SELECT name FROM sqlite_master WHERE type='table' AND name=:t"
            else:
                q = "SELECT tablename AS name FROM pg_tables WHERE schemaname='public' AND tablename=:t"
            has_alembic = (await conn.execute(text(q), {"t": "alembic_version"})).first() is not None
            has_users = (await conn.execute(text(q), {"t": "users"})).first() is not None
            has_version_row = False
            if has_alembic:
                row = (await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))).first()
                has_version_row = row is not None
    finally:
        await engine.dispose()

    if has_version_row:
        return "managed"
    if has_users:
        return "legacy"
    return "fresh"


def _alembic_config():
    from alembic.config import Config
    ini_path = os.path.join(_BACKEND_DIR, "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("script_location", os.path.join(_BACKEND_DIR, "alembic"))
    return cfg


async def run_migrations() -> bool:
    """Stamp (nếu cần) + upgrade head. Trả về True nếu thành công.

    Alembic chạy sync — gọi trong thread để không block event loop lâu.
    """
    import asyncio

    from app.config import get_settings

    settings = get_settings()
    try:
        state = await _detect_state(settings.DATABASE_URL, settings.is_sqlite)
        logger.info("[migrate] DB state: %s", state)

        from alembic import command

        def _run() -> None:
            cfg = _alembic_config()
            if state == "legacy":
                logger.info("[migrate] stamp baseline %s cho DB có sẵn", BASELINE_REV)
                command.stamp(cfg, BASELINE_REV)
            command.upgrade(cfg, "head")

        await asyncio.to_thread(_run)
        logger.info("[migrate] upgrade head OK")
        return True
    except Exception as exc:
        logger.warning("[migrate] migration failed (app vẫn khởi động, create_all fallback): %s", exc)
        return False
