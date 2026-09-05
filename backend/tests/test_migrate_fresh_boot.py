"""Tests cho app/migrate.py — fresh boot không chạy chuỗi migration (vá 05/09/2026).

Lỗi gốc: DB dev sqlite mới tinh đi đường `alembic upgrade head` chết giữa chuỗi
(k01 gọi create_unique_constraint — sqlite không ALTER được constraint) → 9 migration
sau (l01→t01, có cả cột users.llm_api_key) không bao giờ chạy, create_all không bù
cột vào bảng đã tồn tại → app hỏng ngầm ngay sau boot đầu tiên.

Fix 2 tầng: (1) fresh → bỏ qua chuỗi, create_all dựng schema từ models rồi stamp head;
(2) k01 dùng batch_alter_table trên sqlite cho DB dev cũ còn kẹt giữa chuỗi.
"""

import os
import subprocess
import sys

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app import migrate

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.asyncio
class TestDetectState:
    async def test_db_rong_la_fresh(self, tmp_path):
        url = f"sqlite+aiosqlite:///{tmp_path / 'fresh.db'}"
        assert await migrate._detect_state(url, True) == "fresh"

    async def test_db_co_users_chua_alembic_la_legacy(self, tmp_path):
        url = f"sqlite+aiosqlite:///{tmp_path / 'legacy.db'}"
        eng = create_async_engine(url)
        async with eng.begin() as conn:
            await conn.execute(text("CREATE TABLE users (id TEXT PRIMARY KEY)"))
        await eng.dispose()
        assert await migrate._detect_state(url, True) == "legacy"

    async def test_db_da_stamp_la_managed(self, tmp_path):
        url = f"sqlite+aiosqlite:///{tmp_path / 'managed.db'}"
        eng = create_async_engine(url)
        async with eng.begin() as conn:
            await conn.execute(text("CREATE TABLE users (id TEXT PRIMARY KEY)"))
            await conn.execute(text("CREATE TABLE alembic_version (version_num TEXT NOT NULL)"))
            await conn.execute(text("INSERT INTO alembic_version VALUES ('t01_2026a001')"))
        await eng.dispose()
        assert await migrate._detect_state(url, True) == "managed"


@pytest.mark.asyncio
class TestFreshBootKhongChayAlembic:
    async def test_fresh_tra_ve_ngay_khong_dung_alembic(self, monkeypatch):
        """DB mới tinh: run_migrations phải short-circuit TRƯỚC khi đụng alembic."""

        async def _fresh(url, is_sqlite):
            return "fresh"

        monkeypatch.setattr(migrate, "_detect_state", _fresh)

        def _no_alembic():
            raise AssertionError("fresh boot KHÔNG được đụng alembic — create_all lo schema")

        monkeypatch.setattr(migrate, "_alembic_config", _no_alembic)

        assert await migrate.run_migrations() == "fresh"


class TestChuoiMigrationSqlite:
    def test_k01_qua_duoc_tren_sqlite(self, tmp_path):
        """DB dev cũ kẹt giữa chuỗi vẫn phải qua được k01 (batch mode).

        Chạy subprocess vì alembic/env.py đọc DATABASE_URL từ settings đã cache
        trong process — chạy in-process sẽ migrate nhầm vào DB test chung.
        Chỉ upgrade tới k01: các bản sau (n01/o01) dùng raw ALTER viết cho
        Postgres, dev sqlite kẹt ở đó thì xóa file .db là đường chính thức.
        """
        db_file = tmp_path / "chain.db"
        env = {**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///{db_file}"}
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from alembic.config import Config\n"
                "from alembic import command\n"
                "cfg = Config('alembic.ini'); cfg.set_main_option('script_location', 'alembic')\n"
                "command.upgrade(cfg, 'k01_2026a001')\n"
                "print('K01_OK')\n",
            ],
            cwd=BACKEND_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr[-2000:]
        assert "K01_OK" in result.stdout
