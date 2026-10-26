"""NCC: mã số thuế + tên công ty; tạo bù NCC từ tên đã gõ ở mẫu vật tư / báo giá.

26/10/2026. Idempotent.

Revision ID: a17_2026a001
Revises: a16_2026a001
Create Date: 2026-10-26
"""
import re
import uuid
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a17_2026a001'
down_revision: Union[str, Sequence[str], None] = 'a16_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _k(s):
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    co = {c["name"] for c in insp.get_columns("suppliers")}
    if "ma_so_thue" not in co:
        op.add_column("suppliers", sa.Column("ma_so_thue", sa.String(length=20), nullable=True))
    if "ten_cong_ty" not in co:
        op.add_column("suppliers", sa.Column("ten_cong_ty", sa.String(length=255), nullable=True))

    ncc = {}
    for i, n in bind.execute(sa.text("SELECT id, name FROM suppliers")):
        ncc.setdefault(_k(n), i)
    now = datetime.utcnow()  # naive — cột DateTime không tz

    def lay(ten):
        k = _k(ten)
        if not k or k == "ncc chưa rõ":
            return None
        if k not in ncc:
            sid = str(uuid.uuid4())
            bind.execute(sa.text(
                "INSERT INTO suppliers (id, name, category, rating, chiet_khau_pct, notes, is_active, created_at, updated_at) "
                "VALUES (:id, :name, 'general', 5.0, 0, :notes, :act, :now, :now)"
            ), {"id": sid, "name": re.sub(r"\s+", " ", ten.strip())[:255],
                "notes": "Tự tạo từ tên NCC ở Vật tư — bổ sung liên hệ sau", "act": True, "now": now})
            ncc[k] = sid
        return ncc[k]

    for mid, ten in bind.execute(sa.text(
            "SELECT id, ncc_gan_nhat_ten FROM mau_vat_tu WHERE ncc_gan_nhat_id IS NULL AND ncc_gan_nhat_ten IS NOT NULL")).all():
        sid = lay(ten)
        if sid:
            bind.execute(sa.text("UPDATE mau_vat_tu SET ncc_gan_nhat_id = :s WHERE id = :i"), {"s": sid, "i": mid})
    for bid, ten in bind.execute(sa.text(
            "SELECT id, ncc_ten FROM bao_gia_dong_vat_tu WHERE supplier_id IS NULL")).all():
        sid = lay(ten)
        if sid:
            bind.execute(sa.text("UPDATE bao_gia_dong_vat_tu SET supplier_id = :s WHERE id = :i"), {"s": sid, "i": bid})


def downgrade() -> None:
    op.drop_column("suppliers", "ten_cong_ty")
    op.drop_column("suppliers", "ma_so_thue")
