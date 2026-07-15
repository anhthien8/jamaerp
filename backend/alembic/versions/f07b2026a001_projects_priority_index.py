"""spec 07B: index ho tro sort uu tien du an (status, target_end_date, total_value)

Revision ID: f07b2026a001
Revises: dbceffd80f23
Create Date: 2026-07-15
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f07b2026a001'
down_revision: Union[str, Sequence[str], None] = 'dbceffd80f23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.create_index(
            'ix_projects_end_value',
            ['status', 'target_end_date', 'total_value'],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_index('ix_projects_end_value')
