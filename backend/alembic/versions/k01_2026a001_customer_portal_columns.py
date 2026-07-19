"""Customer: portal_token + portal_enabled (bị quên khi thêm Customer Portal)

Revision ID: k01_2026a001
Revises: j01_2026a001
Create Date: 2026-07-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'k01_2026a001'
down_revision: Union[str, Sequence[str], None] = 'j01_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('customers', sa.Column('portal_token', sa.String(length=36), nullable=True))
    op.add_column('customers', sa.Column('portal_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_unique_constraint('uq_customers_portal_token', 'customers', ['portal_token'])


def downgrade() -> None:
    op.drop_constraint('uq_customers_portal_token', 'customers', type_='unique')
    op.drop_column('customers', 'portal_enabled')
    op.drop_column('customers', 'portal_token')
