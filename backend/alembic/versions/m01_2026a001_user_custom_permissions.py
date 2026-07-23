"""User custom_permissions — per-user permission overrides (JSON)

Admin toggle individual permissions per user. Stores JSON string
of {permission_key: boolean} overrides. Custom overrides take
precedence over role defaults.

Revision ID: m01_2026a001
Revises: l01_2026a001
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'm01_2026a001'
down_revision: Union[str, Sequence[str], None] = 'l01_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('custom_permissions', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'custom_permissions')
