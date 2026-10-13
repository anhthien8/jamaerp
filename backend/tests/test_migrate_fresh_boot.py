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


class TestBackfillNguoiDamNhan:
    """z01_2026a001 — backfill `task_assignees` (vá prod 13/10/2026).

    Bản đầu đặt backfill BÊN TRONG nhánh `create_table`, nên khi bảng đã tồn tại
    bằng đường khác (dev `create_all`, hoặc lần chạy trước đã tạo bảng rồi vỡ ở
    bước chèn) thì backfill bị bỏ qua luôn: mọi đầu việc cũ hiện «chưa có ai
    nhận» dù `tasks.assigned_to` vẫn còn tên người. Chạy migration trên DB mới
    tinh KHÔNG bắt được lỗi này vì nhánh create_table luôn chạy.
    """

    @staticmethod
    def _chay_upgrade(conn):
        import importlib.util

        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        duong = os.path.join(
            BACKEND_DIR,
            "alembic",
            "versions",
            "z01_2026a001_nhieu_nguoi_dam_nhan_va_sla_dau_viec.py",
        )
        spec = importlib.util.spec_from_file_location("z01_mig", duong)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            mod.upgrade()

    def _db(self, tmp_path, co_bang_moi: bool):
        """Schema tối thiểu: users + tasks (đã gán người) [+ task_assignees rỗng]."""
        from sqlalchemy import create_engine

        eng = create_engine(f"sqlite:///{tmp_path / 'backfill.db'}")
        with eng.begin() as conn:
            conn.execute(text("CREATE TABLE users (id TEXT PRIMARY KEY)"))
            conn.execute(
                text("CREATE TABLE tasks (id TEXT PRIMARY KEY, assigned_to TEXT)")
            )
            conn.execute(text("INSERT INTO users VALUES ('u1')"))
            conn.execute(text("INSERT INTO tasks VALUES ('t1', 'u1')"))
            # Người đã nghỉ bị xoá khỏi users — không được chèn, kẻo vỡ khoá ngoại.
            conn.execute(text("INSERT INTO tasks VALUES ('t2', 'da-nghi')"))
            if co_bang_moi:
                conn.execute(
                    text(
                        "CREATE TABLE task_assignees ("
                        "id TEXT PRIMARY KEY, task_id TEXT NOT NULL, "
                        "user_id TEXT NOT NULL, created_at DATETIME NOT NULL, "
                        "CONSTRAINT uq_task_assignee UNIQUE (task_id, user_id))"
                    )
                )
        return eng

    def test_bang_da_ton_tai_van_backfill(self, tmp_path):
        eng = self._db(tmp_path, co_bang_moi=True)
        with eng.begin() as conn:
            self._chay_upgrade(conn)
        with eng.connect() as conn:
            rows = conn.execute(
                text("SELECT task_id, user_id FROM task_assignees")
            ).fetchall()
        eng.dispose()
        assert [tuple(r) for r in rows] == [("t1", "u1")]

    def test_chay_lai_khong_nhan_doi(self, tmp_path):
        eng = self._db(tmp_path, co_bang_moi=False)
        for _ in range(2):
            with eng.begin() as conn:
                self._chay_upgrade(conn)
        with eng.connect() as conn:
            dem = conn.execute(text("SELECT COUNT(*) FROM task_assignees")).scalar()
            cols = {
                r[1]
                for r in conn.execute(text("PRAGMA table_info(tasks)")).fetchall()
            }
        eng.dispose()
        assert dem == 1
        assert {"started_at", "sla_due_at"} <= cols

    def test_moc_backfill_khong_mang_timezone(self, tmp_path, monkeypatch):
        """Cột là TIMESTAMP WITHOUT TIME ZONE: mốc có tzinfo làm asyncpg vỡ
        «can't subtract offset-naive and offset-aware datetimes» — đúng lỗi làm
        deploy prod 13/10/2026 rollback cả migration.

        SQLite im lặng bỏ tzinfo nên kiểm chuỗi đã lưu là vô ích: phải bắt chính
        giá trị mà migration đưa cho `op.bulk_insert`.
        """
        from alembic.operations import Operations

        bat_duoc = []
        goc = Operations.bulk_insert

        def _bat(self, table, rows, multiinsert=True):
            bat_duoc.extend(rows)
            return goc(self, table, rows, multiinsert=multiinsert)

        monkeypatch.setattr(Operations, "bulk_insert", _bat)

        eng = self._db(tmp_path, co_bang_moi=False)
        with eng.begin() as conn:
            self._chay_upgrade(conn)
        eng.dispose()

        assert bat_duoc, "không có dòng nào được backfill — test mất tác dụng"
        for dong in bat_duoc:
            assert dong["created_at"].tzinfo is None, dong["created_at"]
