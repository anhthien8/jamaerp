"""spec 09: Zalo Listener — session, groups, messages, signals

Revision ID: h09_2026a001
Revises: g04_2026a001
Create Date: 2026-07-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'h09_2026a001'
down_revision: Union[str, Sequence[str], None] = 'g04_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'zalo_session',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='logged_out'),
        sa.Column('qr_image', sa.Text(), nullable=True),
        sa.Column('account_name', sa.String(length=150), nullable=True),
        sa.Column('error_msg', sa.String(length=500), nullable=True),
        sa.Column('login_requested', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'zalo_groups',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('zalo_group_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False, server_default='internal'),
        sa.Column('assigned_user_id', sa.String(length=36), nullable=True),
        sa.Column('monitoring', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('consent_ref', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['assigned_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('zalo_group_id'),
    )
    with op.batch_alter_table('zalo_groups', schema=None) as batch_op:
        batch_op.create_index('ix_zalo_groups_kind', ['kind'], unique=False)

    op.create_table(
        'zalo_messages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('group_id', sa.String(length=36), nullable=False),
        sa.Column('sender_zalo_id', sa.String(length=64), nullable=True),
        sa.Column('sender_name', sa.String(length=150), nullable=True),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('media_ref', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['zalo_groups.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('zalo_messages', schema=None) as batch_op:
        batch_op.create_index('ix_zalo_messages_group_time', ['group_id', 'created_at'], unique=False)

    op.create_table(
        'zalo_signals',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('group_id', sa.String(length=36), nullable=False),
        sa.Column('source_msg_id', sa.String(length=36), nullable=True),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('summary', sa.String(length=500), nullable=False),
        sa.Column('payload_json', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='new'),
        sa.Column('assigned_user_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['zalo_groups.id']),
        sa.ForeignKeyConstraint(['assigned_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('zalo_signals', schema=None) as batch_op:
        batch_op.create_index('ix_zalo_signals_status', ['status', 'created_at'], unique=False)
        batch_op.create_index('ix_zalo_signals_group', ['group_id'], unique=False)
        batch_op.create_index('ix_zalo_signals_assigned', ['assigned_user_id', 'status'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('zalo_signals', schema=None) as batch_op:
        batch_op.drop_index('ix_zalo_signals_assigned')
        batch_op.drop_index('ix_zalo_signals_group')
        batch_op.drop_index('ix_zalo_signals_status')
    op.drop_table('zalo_signals')

    with op.batch_alter_table('zalo_messages', schema=None) as batch_op:
        batch_op.drop_index('ix_zalo_messages_group_time')
    op.drop_table('zalo_messages')

    with op.batch_alter_table('zalo_groups', schema=None) as batch_op:
        batch_op.drop_index('ix_zalo_groups_kind')
    op.drop_table('zalo_groups')

    op.drop_table('zalo_session')
