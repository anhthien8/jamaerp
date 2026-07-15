"""Nâng cấp schema database an toàn khi deploy.

Xử lý 3 tình huống:
1. DB mới tinh (chưa có bảng nào)          -> alembic upgrade head (tạo full schema)
2. DB cũ đã có bảng nhưng chưa có alembic  -> stamp baseline rồi upgrade head
3. DB đã quản lý bằng alembic              -> alembic upgrade head bình thường

Chạy: python -m scripts.db_upgrade  (từ thư mục backend/)
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.config import get_settings  # noqa: E402

# Revision baseline — schema trước HR phase 1
BASELINE_REV = "ac9de03e7289"


async def detect_state() -> str:
    """Trả về: 'fresh' | 'legacy' | 'managed'."""
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as conn:
            if settings.is_sqlite:
                q = "SELECT name FROM sqlite_master WHERE type='table' AND name=:t"
            else:
                q = "SELECT tablename AS name FROM pg_tables WHERE schemaname='public' AND tablename=:t"
            has_alembic = (await conn.execute(text(q), {"t": "alembic_version"})).first() is not None
            has_users = (await conn.execute(text(q), {"t": "users"})).first() is not None
            # Bảng alembic_version tồn tại nhưng RỖNG (chưa stamp) → vẫn coi là legacy
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


def run_alembic(*args: str) -> None:
    from alembic.config import main as alembic_main
    alembic_main(argv=list(args))


def main() -> None:
    state = asyncio.run(detect_state())
    print(f"[db_upgrade] Trang thai DB: {state}")
    if state == "legacy":
        print(f"[db_upgrade] Stamp baseline {BASELINE_REV} cho DB co san...")
        run_alembic("stamp", BASELINE_REV)
    print("[db_upgrade] alembic upgrade head...")
    run_alembic("upgrade", "head")
    print("[db_upgrade] Xong.")


if __name__ == "__main__":
    main()
