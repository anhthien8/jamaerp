"""Chuẩn hoá số điện thoại + tìm lead trùng (27/10/2026).

Trước đây web / form báo giá công khai / bot mỗi nơi lưu SĐT một kiểu
(«+84 912…», «0912.xxx»), nên cùng một khách thành 2-3 lead của 2-3 sale.
"""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead


def chuan_hoa_sdt(raw: str | None) -> str:
    """«+84 912-345 678» → «0912345678». Chuỗi rỗng nếu không có chữ số."""
    so = re.sub(r"\D", "", raw or "")
    if so.startswith("84") and len(so) >= 11:
        so = "0" + so[2:]
    return so


async def tim_lead_trung(db: AsyncSession, phone: str | None) -> Lead | None:
    """Lead đang sống (chưa thua) có cùng SĐT sau chuẩn hoá."""
    so = chuan_hoa_sdt(phone)
    if len(so) < 8:
        return None
    # 3 số cuối luôn liền nhau kể cả khi lưu «0912.345.678» → lọc thô rồi so chuẩn hoá
    ung_vien = (await db.execute(
        select(Lead).where(Lead.phone.contains(so[-3:]), Lead.stage.notin_(["lost"]))
    )).scalars().all()
    for ld in ung_vien:
        if chuan_hoa_sdt(ld.phone) == so:
            return ld
    return None
