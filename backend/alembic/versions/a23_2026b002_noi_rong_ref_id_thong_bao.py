"""Nới notifications.ref_id từ 36 lên 100 ký tự.

Lỗi 04/11/2026: duyệt cho nhân viên nghỉ việc báo lỗi 500 trên production. Thông báo
cho kế toán dùng ref_id = "offboard-<uuid>" (45 ký tự) > VARCHAR(36) → Postgres từ
chối → cả giao dịch nghỉ việc rollback. Các thông báo phê duyệt ("<uuid>-approved"…),
hết hạn hợp đồng, sinh nhật khách cũng ghép tiền tố/hậu tố nên dính cùng lỗi.

Revision ID: a23_2026b002
Revises: a22_2026b001 (đổi mã 10/11: trùng a21 với link sheet báo giá)
Create Date: 2026-11-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a23_2026b002'
down_revision: Union[str, Sequence[str], None] = 'a22_2026b001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.alter_column("ref_id", existing_type=sa.String(length=36),
                              type_=sa.String(length=100), existing_nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.alter_column("ref_id", existing_type=sa.String(length=100),
                              type_=sa.String(length=36), existing_nullable=True)
