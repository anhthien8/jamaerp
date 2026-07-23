"""Widen system_settings.value to Text for custom_roles JSON storage

Revision ID: n01_2026a001
Revises: m01_2026a001
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'n01_2026a001'
down_revision: Union[str, Sequence[str], None] = 'm01_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('system_settings', 'value', type_=sa.Text(), existing_type=sa.String(500))


def downgrade() -> None:
    op.alter_column('system_settings', 'value', type_=sa.String(500), existing_type=sa.Text())
