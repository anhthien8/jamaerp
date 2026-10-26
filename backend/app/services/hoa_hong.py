"""Mức hoa hồng hợp đồng — đọc từ cơ cấu hoa hồng đã được BGĐ duyệt.

Chủ dự án chốt 26/10/2026: kế toán/admin đặt mức mới kèm ngày hiệu lực trên trang
Tài chính › Cơ cấu hoa hồng, mức đó chỉ áp dụng sau khi Ban giám đốc duyệt (qua
mục Phê duyệt chung). Chưa có mức nào được duyệt thì giữ đúng mức cũ 3% / 2%.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commission_structure import (
    TRANG_THAI_CHO_DUYET,
    TRANG_THAI_DA_DUYET,
    TRANG_THAI_TU_CHOI,
    CommissionStructure,
)
from app.models.user import User
from app.services import approval_engine

LOAI_DUYET = "commission_rate"
# Mức cũ trước 26/10/2026 — dùng khi chưa có cơ cấu nào được duyệt
MUC_MAC_DINH = {"design_commission": 0.03, "construction_commission": 0.02}
# Bảng cơ cấu dùng cả hai cách gọi (seed ghi *_contract, bản ghi hoa hồng ghi *_commission)
_TEN_KHAC = {"design_commission": "design_contract", "construction_commission": "construction_contract"}


async def muc_hoa_hong(db: AsyncSession, loai: str, ngay: date) -> float:
    """Tỷ lệ (0.03 = 3%) của phòng Sale cho `loai`, mức đã duyệt mới nhất có hiệu lực tới `ngay`."""
    rate = (await db.execute(
        select(CommissionStructure.rate)
        .where(
            CommissionStructure.department == "sales",
            CommissionStructure.commission_type.in_((loai, _TEN_KHAC[loai])),
            CommissionStructure.status == TRANG_THAI_DA_DUYET,
            CommissionStructure.effective_date <= ngay,
        )
        .order_by(CommissionStructure.effective_date.desc(), CommissionStructure.approved_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    # Bảng lưu dạng tỷ lệ (0.03 = 3%), giống seed và trang Tài chính
    return rate if rate is not None else MUC_MAC_DINH[loai]


async def gui_duyet(db: AsyncSession, cs: CommissionStructure, actor: User) -> None:
    """Tạo đơn chờ Ban giám đốc duyệt. Người duyệt: tài khoản BGĐ (executive), không có thì admin."""
    nguoi_duyet = (await db.execute(
        select(User.id)
        .where(User.is_active == True, User.role.in_(("executive", "admin")), User.id != actor.id)  # noqa: E712
        .order_by(User.role.desc())  # "executive" xếp trước "admin"
        .limit(1)
    )).scalar_one_or_none()
    don = await approval_engine.create_request(
        db, type_=LOAI_DUYET, ref_id=cs.id,
        title=f"Hoa hồng {cs.commission_type} phòng {cs.department}: {cs.rate * 100:g}% từ {cs.effective_date:%d/%m/%Y}",
        requester=actor, approver_ids=[nguoi_duyet] if nguoi_duyet else [], sla_hours=72,
    )
    cs.status = TRANG_THAI_CHO_DUYET
    cs.approval_id = don.id
    await db.flush()


async def _on_duyet(db: AsyncSession, request) -> None:
    cs = await db.get(CommissionStructure, request.ref_id)
    if cs is not None:
        cs.status = TRANG_THAI_DA_DUYET
        cs.approved_at = datetime.now(timezone.utc)
        await db.flush()


async def _on_tu_choi(db: AsyncSession, request) -> None:
    cs = await db.get(CommissionStructure, request.ref_id)
    if cs is not None:
        cs.status = TRANG_THAI_TU_CHOI
        await db.flush()


approval_engine.TYPE_LABELS.setdefault(LOAI_DUYET, "Cơ cấu hoa hồng")
approval_engine.register_side_effect(LOAI_DUYET, _on_duyet)
approval_engine.register_reject_effect(LOAI_DUYET, _on_tu_choi)
