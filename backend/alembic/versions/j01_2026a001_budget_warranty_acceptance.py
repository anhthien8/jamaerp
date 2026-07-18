"""Project: budget_total + handover_date/warranty_months + stage_acceptances

Revision ID: j01_2026a001
Revises: i01_2026a001
Create Date: 2026-07-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'j01_2026a001'
down_revision: Union[str, Sequence[str], None] = 'i01_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('budget_total', sa.Float(), nullable=True))
    op.add_column('projects', sa.Column('handover_date', sa.DateTime(), nullable=True))
    op.add_column('projects', sa.Column('warranty_months', sa.Integer(), nullable=False, server_default='12'))
    op.add_column('projects', sa.Column('stage_acceptances', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'stage_acceptances')
    op.drop_column('projects', 'warranty_months')
    op.drop_column('projects', 'handover_date')
    op.drop_column('projects', 'budget_total')
