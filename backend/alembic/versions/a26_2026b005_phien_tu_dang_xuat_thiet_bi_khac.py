"""Phiên đăng nhập 7 ngày: cột users.phien_tu — mốc huỷ token cũ.

Token (JWT) có iat trước users.phien_tu bị từ chối. Mốc được ghi khi đổi/đặt lại
mật khẩu và khi người dùng bấm «Đăng xuất các thiết bị khác». Cột để trống
(NULL) = chưa từng huỷ phiên → không ai bị đăng xuất khi chạy migration này.

Revision ID: a26_2026b005
Revises: a25_2026b004
Create Date: 2026-11-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a26_2026b005'
down_revision: Union[str, Sequence[str], None] = 'a25_2026b004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    da_co = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}
    if "phien_tu" not in da_co:
        # DateTime không múi giờ — mã ghi mốc naive UTC (moc_phien_moi)
        op.add_column("users", sa.Column("phien_tu", sa.DateTime(), nullable=True))


def downgrade() -> None:
    da_co = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}
    if "phien_tu" in da_co:
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("phien_tu")
