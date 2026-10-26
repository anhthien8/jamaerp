"""OT không cần duyệt: OT đang chờ → đã ghi nhận (26/10/2026)

Revision ID: a18_2026a001
Revises: a17_2026a001
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'a18_2026a001'
down_revision: Union[str, Sequence[str], None] = 'a17_2026a001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE attendance_records SET ot_status = 'approved' WHERE ot_status = 'pending'")


def downgrade() -> None:
    pass
