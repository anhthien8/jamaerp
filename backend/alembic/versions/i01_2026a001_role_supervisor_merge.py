"""Merge designer/purchasing/pm roles into supervisor

Revision ID: i01_2026a001
Revises: h09_2026a001
Create Date: 2026-07-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'i01_2026a001'
down_revision: Union[str, Sequence[str], None] = 'h09_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert existing users from old roles to supervisor
    op.execute("UPDATE users SET role = 'supervisor' WHERE role IN ('designer', 'purchasing', 'pm')")

    # Update task coordinator preferred_role references
    op.execute("UPDATE tasks SET assigned_to = NULL WHERE assigned_to IN (SELECT id FROM users WHERE role = 'supervisor')")

    # Update commission structures
    op.execute("UPDATE commission_structures SET department = 'supervisor' WHERE department IN ('designer', 'purchasing', 'pm', 'design', 'pm')")


def downgrade() -> None:
    # Cannot perfectly reverse — old role assignments are lost
    # Set back to 'data_entry' as safest fallback
    op.execute("UPDATE users SET role = 'data_entry' WHERE role = 'supervisor'")
    op.execute("UPDATE commission_structures SET department = 'sales' WHERE department = 'supervisor'")
