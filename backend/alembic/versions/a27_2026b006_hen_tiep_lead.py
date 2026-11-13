"""Hẹn tiếp của lead (R00): cột leads.hen_tiep_luc.

Lúc sale hẹn gọi/gặp lại khách (bấm «Hẹn lại» trên tin Telegram hoặc chip web).
Hẹn còn ở tương lai → job nhắc chăm sóc và thu hồi lead bỏ qua lead đó.
Naive giờ VN như `survey_date`. Cột trống với mọi lead cũ → không đổi gì khi chạy.

Revision ID: a27_2026b006
Revises: a26_2026b005
Create Date: 2026-11-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a27_2026b006'
down_revision: Union[str, Sequence[str], None] = 'a26_2026b005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    da_co = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("leads")}
    if "hen_tiep_luc" not in da_co:
        # DateTime không múi giờ — mã ghi giờ VN naive (như survey_date)
        op.add_column("leads", sa.Column("hen_tiep_luc", sa.DateTime(), nullable=True))


def downgrade() -> None:
    da_co = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("leads")}
    if "hen_tiep_luc" in da_co:
        with op.batch_alter_table("leads") as batch_op:
            batch_op.drop_column("hen_tiep_luc")
