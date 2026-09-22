"""Cột leads.ngan_sach_khoang — Ngân sách theo 3 mức.

Chủ dự án yêu cầu 22/09: form thêm lead có ô «Ngân sách» chọn 1 trong 3 mức
(dưới 200 triệu / 200–500 triệu / trên 500 triệu).

Đo prod trước khi làm: cột `estimated_budget` (số tiền) đã có và 79/615 lead có
số thật. Nên KHÔNG thay cột đó bằng khoảng — thêm cột mức riêng, giữ cột số cho
79 lead cũ và cho báo giá/hợp đồng dùng (chốt với chủ dự án).

Revision ID: y01_2026a001
Revises: x01_2026a001
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'y01_2026a001'
down_revision: Union[str, Sequence[str], None] = 'x01_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "leads" not in set(insp.get_table_names()):
        return
    cols = {c["name"] for c in insp.get_columns("leads")}
    if "ngan_sach_khoang" not in cols:
        op.add_column("leads", sa.Column("ngan_sach_khoang", sa.String(length=20), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "leads" not in set(insp.get_table_names()):
        return
    cols = {c["name"] for c in insp.get_columns("leads")}
    if "ngan_sach_khoang" in cols:
        op.drop_column("leads", "ngan_sach_khoang")
