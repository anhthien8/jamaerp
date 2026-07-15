"""spec 04: performance — kpi_snapshots, coaching_notes, review_cycles

Revision ID: g04_2026a001
Revises: f07b2026a001
Create Date: 2026-07-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'g04_2026a001'
down_revision: Union[str, Sequence[str], None] = 'f07b2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # kpi_snapshots
    op.create_table(
        'kpi_snapshots',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('period', sa.String(10), nullable=False),
        sa.Column('metrics_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('score', sa.Float(), nullable=False, server_default='0'),
        sa.Column('rank_in_team', sa.Integer(), nullable=True),
        sa.Column('rank_overall', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_kpi_user_period', 'kpi_snapshots', ['user_id', 'period'], unique=True)

    # coaching_notes
    op.create_table(
        'coaching_notes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('coach_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('kind', sa.String(20), nullable=False, server_default='one_on_one'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_coaching_user', 'coaching_notes', ['user_id', 'created_at'])

    # review_cycles
    op.create_table(
        'review_cycles',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('period', sa.String(7), nullable=False),
        sa.Column('self_json', sa.Text(), nullable=True),
        sa.Column('leader_json', sa.Text(), nullable=True),
        sa.Column('goals_json', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending_self'),
        sa.Column('suggested_grade_change', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_review_user_period', 'review_cycles', ['user_id', 'period'], unique=True)


def downgrade() -> None:
    op.drop_table('review_cycles')
    op.drop_table('coaching_notes')
    op.drop_table('kpi_snapshots')
