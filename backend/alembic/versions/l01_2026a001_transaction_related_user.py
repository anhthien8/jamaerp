"""Transaction: related_user_id — liên kết nhân viên cho giao dịch Lương/Hoa hồng

Schema TransactionCreate đã có user_id từ đầu nhưng model/endpoint bỏ quên không dùng
(kế toán không gắn được giao dịch lương với nhân viên nào — feedback user 22/07).

Revision ID: l01_2026a001
Revises: k01_2026a001
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'l01_2026a001'
down_revision: Union[str, Sequence[str], None] = 'k01_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Không tạo FK constraint tường minh: SQLite không ALTER được FK,
    # còn logic join tên nhân viên xử lý ở tầng API (an toàn khi user bị xóa).
    op.add_column('transactions', sa.Column('related_user_id', sa.String(length=36), nullable=True))
    op.create_index('ix_transactions_related_user', 'transactions', ['related_user_id'])


def downgrade() -> None:
    op.drop_index('ix_transactions_related_user', table_name='transactions')
    op.drop_column('transactions', 'related_user_id')
