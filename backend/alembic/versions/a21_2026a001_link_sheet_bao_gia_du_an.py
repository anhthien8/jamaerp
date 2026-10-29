"""Link Google Sheet báo giá của dự án.

30/10/2026: bot Telegram thôi nhận tệp báo giá (tệp tổng hợp nặng 15 MB, sát
giới hạn 20 MB của bot) — người dùng gửi LINK Google Sheet chia sẻ công khai,
hệ thống tự tải về đọc và lưu link vào dự án để mọi người mở lại được.

Revision ID: a21_2026a001
Revises: a20_2026a001
Create Date: 2026-10-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a21_2026a001'
down_revision: Union[str, Sequence[str], None] = 'a20_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("bao_gia_sheet_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "bao_gia_sheet_url")
