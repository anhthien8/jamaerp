"""Cột leads.lost_reason — lý do mất lead.

Giao diện có sẵn khối chọn lý do («Ngân sách không phù hợp», «Đã chọn đối thủ»,
…) và thẻ chi tiết có khối hiển thị «Lý do mất lead» từ lâu, nhưng backend chưa
hề có chỗ chứa: không cột, không schema, không trả trong response. Hệ quả là
bấm «Chuyển sang Mất lead» thì `PUT /leads/{id}` nhận `{stage, lost_reason}`,
Pydantic bỏ qua cả hai (LeadUpdate không khai báo, không đặt extra='forbid') →
trả 200 với lead y nguyên → user thấy báo thành công mà lead vẫn ở cột cũ.

Nay lý do được lưu thật và mọi chuyển giai đoạn đi qua PUT /leads/{id}/stage.

Cùng kiểu phòng thủ như o01→s01: kiểm tra tồn tại trước khi thao tác nên chạy
lại an toàn trên cả dev SQLite (create_all đã tạo sẵn cột) lẫn prod Postgres.

Revision ID: t01_2026a001
Revises: s01_2026a001
Create Date: 2026-08-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 't01_2026a001'
down_revision: Union[str, Sequence[str], None] = 's01_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "leads" not in set(insp.get_table_names()):
        return
    cols = {c["name"] for c in insp.get_columns("leads")}
    if "lost_reason" not in cols:
        op.add_column("leads", sa.Column("lost_reason", sa.String(length=255), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "leads" not in set(insp.get_table_names()):
        return
    cols = {c["name"] for c in insp.get_columns("leads")}
    if "lost_reason" in cols:
        op.drop_column("leads", "lost_reason")
