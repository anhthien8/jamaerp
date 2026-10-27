"""Dòng vật tư: ngày cần hàng (27/10/2026)

Revision ID: a19_2026a001
Revises: a18_2026a001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a19_2026a001'
down_revision: Union[str, Sequence[str], None] = 'a18_2026a001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dong_phieu_vat_tu", sa.Column("can_ngay", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("dong_phieu_vat_tu", "can_ngay")
