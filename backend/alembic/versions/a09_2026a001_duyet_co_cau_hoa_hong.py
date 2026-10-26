"""Cơ cấu hoa hồng phải được BGĐ duyệt mới có hiệu lực.

Chủ dự án yêu cầu 26/10/2026: mức hoa hồng chỉnh được trên giao diện kèm ngày
hiệu lực, nhưng chỉ áp dụng sau khi Ban giám đốc xác nhận. Trước đó hợp đồng ký
xong luôn tính cứng 3% thiết kế / 2% thi công, bảng này không ai đọc.

Dòng cũ để `cho_duyet`: chúng chưa từng được áp dụng, không thể tự coi là đã duyệt
— kế toán bấm «Gửi duyệt» nếu vẫn muốn dùng.

Revision ID: a09_2026a001
Revises: a08_2026a001
Create Date: 2026-10-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a09_2026a001'
down_revision: Union[str, Sequence[str], None] = 'a08_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "commission_structures" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("commission_structures")}
    if "status" not in cols:
        op.add_column("commission_structures", sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="cho_duyet"))
    if "approval_id" not in cols:
        op.add_column("commission_structures", sa.Column("approval_id", sa.String(length=36), nullable=True))
    if "approved_at" not in cols:
        op.add_column("commission_structures", sa.Column("approved_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    for col in ("approved_at", "approval_id", "status"):
        op.drop_column("commission_structures", col)
