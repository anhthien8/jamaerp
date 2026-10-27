"""Phụ lục hợp đồng: HĐ con trỏ về HĐ gốc (27/10/2026)

Revision ID: a20_2026a001
Revises: a19_2026a001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a20_2026a001'
down_revision: Union[str, Sequence[str], None] = 'a19_2026a001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contracts", sa.Column("parent_contract_id", sa.String(36), nullable=True))
    op.create_index("ix_contracts_parent_contract_id", "contracts", ["parent_contract_id"])


def downgrade() -> None:
    op.drop_index("ix_contracts_parent_contract_id", "contracts")
    op.drop_column("contracts", "parent_contract_id")
