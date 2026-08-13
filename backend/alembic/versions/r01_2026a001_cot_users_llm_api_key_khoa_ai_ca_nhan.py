"""Cột users.llm_api_key — khóa AI cá nhân, ưu tiên trước key hệ thống.

Hệ thống có key Groq chung (Railway env LLM_API_KEY, admin đổi được qua UI
Cài đặt). User nào thêm key riêng thì mọi lời gọi AI trong request của họ
dùng key đó TRƯỚC, lỗi mới rơi về key chung — ai xài nhiều không đốt quota
free tier của cả công ty.

Cùng kiểu phòng thủ như o01/p01/q01: kiểm tra tồn tại trước mỗi thao tác nên
chạy lại an toàn trên cả dev SQLite (create_all đã tạo sẵn cột) lẫn prod Postgres.

Revision ID: r01_2026a001
Revises: q01_2026a001
Create Date: 2026-08-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'r01_2026a001'
down_revision: Union[str, Sequence[str], None] = 'q01_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("users")}
    if "llm_api_key" not in cols:
        op.add_column("users", sa.Column("llm_api_key", sa.String(length=255), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("users")}
    if "llm_api_key" in cols:
        op.drop_column("users", "llm_api_key")
