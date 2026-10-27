"""Đồng bộ tiền giữa Hợp đồng ↔ Dự án ↔ Tài chính ↔ P&L (27/10/2026).

Trước đây mỗi màn hình một số: bấm «Đã thu» không sinh giao dịch thu (kế toán
nhập lại ở Tài chính), sửa giá trị HĐ không về dự án (Hũ thưởng, Bảng KD đọc
dự án), vật tư đã đặt không bao giờ vào `Project.spent` nên cảnh báo vượt
ngân sách vô hiệu.
"""

from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract
from app.models.payroll import Transaction
from app.models.project import Project

# Dòng vật tư đã cam kết tiền với NCC
TRANG_THAI_TON_TIEN = ("da_dat", "da_giao")
# Đợt có tiền về: thu đủ hoặc thu một phần
TRANG_THAI_CO_TIEN = ("paid", "partial")


def ma_giao_dich_thu(contract: Contract, idx: int) -> str:
    return f"THU-{contract.code}-D{idx + 1}"[:50]


async def dong_bo_gia_tri_du_an(db: AsyncSession, project_id: str | None) -> None:
    """Giá trị dự án = tổng giá trị các HĐ không huỷ (kể cả phụ lục)."""
    if not project_id:
        return
    tong = (await db.execute(
        select(func.coalesce(func.sum(Contract.total_value), 0))
        .where(Contract.project_id == project_id, Contract.status != "cancelled")
    )).scalar() or 0
    co_hd = (await db.execute(select(func.count(Contract.id)).where(Contract.project_id == project_id))).scalar()
    p = await db.get(Project, project_id)
    # Còn HĐ (kể cả đã huỷ hết → 0); dự án chưa có HĐ nào thì giữ giá trị nhập tay
    if p and co_hd and float(p.total_value or 0) != float(tong):
        p.total_value = float(tong)


async def ghi_giao_dich_thu(db: AsyncSession, contract: Contract, idx: int, user_id: str | None) -> None:
    """Đợt có tiền về → 1 giao dịch thu (cập nhật nếu đã có); bỏ thu → huỷ giao dịch."""
    from app.services.hoa_hong import tien_dot

    inst = ((contract.payment_terms or {}).get("installments") or [])[idx]
    ma = ma_giao_dich_thu(contract, idx)
    gd = (await db.execute(select(Transaction).where(Transaction.code == ma))).scalars().first()
    co_tien = inst.get("status") in TRANG_THAI_CO_TIEN
    if not co_tien:
        if gd:
            gd.status = "cancelled"
        return
    so_tien = tien_dot(contract, idx)
    try:
        ngay = datetime.combine(date.fromisoformat(str(inst.get("paid_date"))[:10]), datetime.min.time())
    except (TypeError, ValueError):
        ngay = datetime.now(timezone.utc).replace(tzinfo=None)
    loai = "design_contract" if (contract.contract_kind == "thiet_ke") else "construction_contract"
    mo_ta = f"Thu {inst.get('name') or f'đợt {idx + 1}'} — HĐ {contract.code}"[:500]
    if gd:
        gd.amount, gd.date, gd.status, gd.description = so_tien, ngay, "completed", mo_ta
    else:
        db.add(Transaction(
            code=ma, type="income", category=loai, description=mo_ta, amount=so_tien,
            project_id=contract.project_id, created_by=user_id, status="completed", date=ngay,
        ))


async def chi_phi_vat_tu(db: AsyncSession, project_id: str | None = None) -> dict[str, float]:
    """{project_id: Σ giá vốn × số lượng} các dòng vật tư đã đặt/đã giao."""
    from app.models.vat_tu import DongPhieuVatTu

    q = (
        select(DongPhieuVatTu.project_id,
               func.coalesce(func.sum(DongPhieuVatTu.gia_von * DongPhieuVatTu.so_luong), 0))
        .where(DongPhieuVatTu.trang_thai.in_(TRANG_THAI_TON_TIEN), DongPhieuVatTu.gia_von.is_not(None))
        .group_by(DongPhieuVatTu.project_id)
    )
    if project_id:
        q = q.where(DongPhieuVatTu.project_id == project_id)
    return {pid: float(v) for pid, v in (await db.execute(q)).all()}


async def tinh_lai_spent(db: AsyncSession, project_id: str | None) -> None:
    """Project.spent = vật tư đã đặt + giao dịch chi gắn dự án (không huỷ)."""
    if not project_id:
        return
    vt = (await chi_phi_vat_tu(db, project_id)).get(project_id, 0.0)
    chi = (await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(Transaction.project_id == project_id, Transaction.type == "expense",
               Transaction.status != "cancelled")
    )).scalar() or 0
    p = await db.get(Project, project_id)
    if p:
        p.spent = float(vt) + float(chi)
