"""Database setup — async SQLAlchemy engine + session (SQLite/PostgreSQL)."""

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# SQLite doesn't support pool_size/max_overflow
engine_kwargs = {"echo": settings.DEBUG}
if settings.is_sqlite:
    engine_kwargs["connect_args"] = {"timeout": 15}
else:
    engine_kwargs.update({
        "pool_size": 20,
        "max_overflow": 10,
        "pool_pre_ping": True,
    })

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

# Enable WAL mode + busy_timeout for SQLite
if settings.is_sqlite:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=10000;")
        cursor.close()
else:
    # PostgreSQL/asyncpg: codebase dùng datetime.now(timezone.utc) (tz-aware)
    # nhưng cột khai báo DateTime naive (TIMESTAMP WITHOUT TIME ZONE) — asyncpg
    # từ chối bind tz-aware vào cột naive. Codec này tự quy về UTC-naive khi ghi,
    # áp dụng cho MỌI câu lệnh mà không phải sửa từng model/endpoint.
    @event.listens_for(engine.sync_engine, "connect")
    def _register_pg_timestamp_codec(dbapi_connection, connection_record):
        import datetime as _dt

        def _encode_ts(value):
            if isinstance(value, _dt.datetime) and value.tzinfo is not None:
                value = value.astimezone(_dt.timezone.utc).replace(tzinfo=None)
            return value.isoformat(sep=" ")

        def _decode_ts(value: str):
            return _dt.datetime.fromisoformat(value)

        async def _setup(conn):
            await conn.set_type_codec(
                "timestamp",
                encoder=_encode_ts,
                decoder=_decode_ts,
                schema="pg_catalog",
                format="text",
            )

        dbapi_connection.run_async(_setup)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


async def get_db():
    """FastAPI dependency — yields async DB session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
