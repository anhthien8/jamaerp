"""Chế độ thưởng: bảng khách hàng chấm sao trên trang tiến độ.

23/10/2026. Cấu hình thưởng nằm ở system_settings (không cần schema); chỉ
điểm đánh giá của khách cần bảng riêng. Tạo nếu chưa có — không backfill.

Revision ID: a07_2026a001
Revises: a06_2026a001
Create Date: 2026-10-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a07_2026a001'
down_revision: Union[str, Sequence[str], None] = 'a06_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if "danh_gia_khach" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "danh_gia_khach",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("customer_id", sa.String(length=36), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("moc", sa.String(length=20), nullable=False),
        sa.Column("so_sao", sa.Integer(), nullable=False),
        sa.Column("nhan_xet", sa.Text(), nullable=True),
        sa.Column("khen_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("project_id", "moc", name="uq_danh_gia_du_an_moc"),
    )
    op.create_index("ix_danh_gia_khach_project_id", "danh_gia_khach", ["project_id"])
    op.create_index("ix_danh_gia_khach_created_at", "danh_gia_khach", ["created_at"])


def downgrade() -> None:
    op.drop_table("danh_gia_khach")
