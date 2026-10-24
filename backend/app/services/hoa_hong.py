"""Hoa hồng tự động theo JD công ty (dựng 24/10/2026).

Nguồn: JD từng vị trí + chính sách hoa hồng trưởng phòng (tài liệu nội bộ, không
lưu trong repo). Chỉ giữ ở đây TỶ LỆ và MỐC TRẢ — đủ để máy tính, không chép văn bản.

Ba sự kiện kích hoạt (gọi từ api/contracts.py):
- Kế toán tích «đã thu» một đợt  → khi_thu_tien()
- Hợp đồng chuyển «đã ký»         → khi_ky_hop_dong()
- Hợp đồng chuyển «hoàn thành»    → khi_nghiem_thu()   (= nghiệm thu bàn giao)
Bỏ tích «đã thu» → khi_bo_thu_tien() gỡ các dòng CHƯA duyệt của đợt đó.

| Ai                         | Tỷ lệ               | Trên            | Khi nào được tính lương                 |
|----------------------------|---------------------|-----------------|-----------------------------------------|
| Sale (sales_id)            | 1% / 2% khách riêng | tiền từng đợt   | tháng khách trả đợt đó                  |
| Trưởng phòng KD            | 0,2%                | tiền từng đợt   | tháng khách trả đợt đó                  |
| Thiết kế (designer_id)     | 0,5% chủ trì / 0,3% | tiền từng đợt   | đợt 1–2: khi khách trả đợt 2;           |
| Trưởng phòng Thiết kế      | 0,2%                | (HĐ thi công)   | đợt 3 trở đi: khi nghiệm thu            |
| Thu mua (purchasing_id)    | 0,1%                | giá trị HĐ thi công | 50% khi ký, 50% khi nghiệm thu      |
| Trưởng phòng Báo giá       | 0,2%                | giá trị HĐ thi công | 50% khi ký, 50% khi nghiệm thu      |
| Giám sát (pm_id)           | 0,5%                | giá trị HĐ thi công | khi nghiệm thu                      |
| Trưởng phòng Giám sát      | 0,2%                | giá trị HĐ thi công | khi nghiệm thu                      |

Trạng thái: «cho_moc» (chưa tới mốc, chưa có kỳ) → «pending» (đã có kỳ, chờ kế
toán duyệt) → «approved» (vào bảng lương kỳ đó) → «paid».
Admin/BGĐ không nhận hoa hồng (108/153 dự án cũ đang gắn sale = tài khoản admin).
Trưởng phòng chỉ hưởng 0,2% khi dự án có người phòng mình phụ trách (PIC thật).

Chưa làm (đợt sau): thưởng nóng không giảm giá, thưởng doanh số tháng/6 tháng,
phạt lỗi thiết kế, trừ phần thô khi tính 0,2% TP KD, Trưởng nhóm thu mua 0,1%.
"""

from __future__ import annotations

import unicodedata
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.rbac import VAI_TRO_TRUONG_NHOM, VAI_TRO_TRUONG_PHONG
from app.models.contract import Contract
from app.models.employee_profile import EmployeeProfile
from app.models.payroll import Commission
from app.models.project import Project
from app.models.user import User
from app.services.attendance_service import period_of, vn_today

TY_LE_SALE = 0.01
TY_LE_SALE_KHACH_RIENG = 0.02
TY_LE_TP_KD = 0.002
TY_LE_THIET_KE_CHU_TRI = 0.005
TY_LE_THIET_KE = 0.003
TY_LE_TP_THIET_KE = 0.002
TY_LE_THU_MUA = 0.001
TY_LE_TP_BAO_GIA = 0.002
TY_LE_GIAM_SAT = 0.005
TY_LE_TP_GIAM_SAT = 0.002

# Đợt thứ 2 (index 1) — mốc trả hoa hồng thiết kế lần 1
IDX_DOT_2 = 1

# Nhãn tiếng Việt cho từng loại (FE có bản song song trong lib/hoa-hong.ts)
TEN_LOAI = {
    "hh_sale": "Hoa hồng sale",
    "hh_tp_kd": "Trưởng phòng KD",
    "hh_thiet_ke": "Hoa hồng thiết kế",
    "hh_tp_thiet_ke": "Trưởng phòng Thiết kế",
    "hh_thu_mua": "Hoa hồng thu mua",
    "hh_tp_bao_gia": "Trưởng phòng Báo giá",
    "hh_giam_sat": "Hoa hồng giám sát",
    "hh_tp_giam_sat": "Trưởng phòng Giám sát",
}


def _bo_dau(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D").lower()


def loai_hop_dong(contract: Contract) -> str:
    """thiet_ke | thi_cong. Kế toán chọn trên form; trống thì đoán theo tiêu đề
    (mẫu HĐ công ty: «HỢP ĐỒNG THIẾT KẾ …» / «HỢP ĐỒNG THI CÔNG …»)."""
    if contract.contract_kind in ("thiet_ke", "thi_cong"):
        return contract.contract_kind
    t = _bo_dau(f"{contract.title or ''} {contract.code or ''}")
    if "thiet ke" in t and "thi cong" not in t:
        return "thiet_ke"
    return "thi_cong"


def _thang_sau(ky: str) -> str:
    y, m = int(ky[:4]), int(ky[5:7])
    y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"{y:04d}-{m:02d}"


def _dot(contract: Contract) -> list[dict]:
    return (contract.payment_terms or {}).get("installments", []) or []


def _da_thu(inst: dict) -> bool:
    return (inst or {}).get("status") == "paid"


def tien_dot(contract: Contract, idx: int) -> float:
    """Số tiền một đợt: ưu tiên số kế toán nhập khi tích «đã thu», không có thì
    tính theo % của giá trị HĐ."""
    inst = _dot(contract)[idx]
    if inst.get("amount"):
        return float(inst["amount"])
    return float(contract.total_value or 0) * float(inst.get("percentage") or 0) / 100.0


def _ky_cua_dot(inst: dict) -> str:
    try:
        return period_of(date.fromisoformat(str(inst.get("paid_date"))[:10]))
    except (TypeError, ValueError):
        return period_of(vn_today())


async def _nguoi(db: AsyncSession, user_id: str | None) -> User | None:
    if not user_id:
        return None
    u = await db.get(User, user_id)
    if not u or not u.is_active or u.role in ("admin", "executive"):
        return None
    return u


async def _truong_phong(db: AsyncSession, dept: str) -> User | None:
    vai = VAI_TRO_TRUONG_PHONG.get(dept, set())
    rows = (await db.execute(
        select(User).where(
            User.is_active == True,  # noqa: E712
            User.role.in_(vai),
            User.department == dept,
        ).order_by(User.created_at)
    )).scalars().all()
    return rows[0] if rows else None


class _Ghi:
    """Gom thao tác tạo dòng hoa hồng của một sự kiện — idempotent theo khóa
    (HĐ, đợt, mốc, loại, người) để tích đi tích lại không nhân đôi."""

    def __init__(self, db: AsyncSession, contract: Contract, project: Project):
        self.db = db
        self.contract = contract
        self.project = project
        self.tao: list[Commission] = []

    async def them(
        self, user: User | None, loai: str, rate: float, base: float, *,
        milestone: str, idx: int | None = None, pct: float = 1.0,
        ky: str | None = None, note: str | None = None,
    ) -> None:
        if not user or base <= 0:
            return
        da_co = (await self.db.execute(
            select(Commission.id).where(
                Commission.contract_id == self.contract.id,
                Commission.installment_idx.is_(None) if idx is None else Commission.installment_idx == idx,
                Commission.milestone == milestone,
                Commission.type == loai,
                Commission.user_id == user.id,
            ).limit(1)
        )).first()
        if da_co:
            return
        c = Commission(
            user_id=user.id,
            project_id=self.project.id,
            contract_id=self.contract.id,
            installment_idx=idx,
            type=loai,
            rate=rate,
            base_amount=round(base),
            commission_amount=round(base * rate * pct),
            milestone=milestone,
            milestone_pct=pct,
            status="pending" if ky else "cho_moc",
            period=ky,
            note=note,
        )
        self.db.add(c)
        self.tao.append(c)

    async def bao(self) -> None:
        """Mỗi người nhận 1 thông báo cho cả sự kiện (không spam từng dòng)."""
        if not self.tao:
            return
        await self.db.flush()
        from app.services.automation import _notify

        theo_nguoi: dict[str, float] = {}
        for c in self.tao:
            theo_nguoi[c.user_id] = theo_nguoi.get(c.user_id, 0) + c.commission_amount
        for uid, tong in theo_nguoi.items():
            u = await self.db.get(User, uid)
            await _notify(
                self.db, u, "commission_created",
                f"Hoa hồng mới từ hợp đồng {self.contract.code}",
                f"Dự kiến {tong:,.0f}đ (chờ kế toán duyệt). Xem ở Hồ sơ 360° → tab Tiền.".replace(",", "."),
                link=f"/hr/nhan-vien?id={uid}",
                ref_id=self.contract.id,
            )


async def _ghi_cho(db: AsyncSession, contract: Contract) -> _Ghi | None:
    project = await db.get(Project, contract.project_id)
    return _Ghi(db, contract, project) if project else None


async def _ghi_chu_thu_viec(db: AsyncSession, user: User | None) -> str | None:
    if not user:
        return None
    p = (await db.execute(
        select(EmployeeProfile.contract_type).where(EmployeeProfile.user_id == user.id)
    )).scalar_one_or_none()
    return "Đang thử việc — JD thu mua chỉ tính sau thử việc, kế toán xem lại" if p == "probation" else None


async def khi_thu_tien(db: AsyncSession, contract: Contract, idx: int) -> None:
    g = await _ghi_cho(db, contract)
    if not g:
        return
    dots = _dot(contract)
    inst = dots[idx]
    tien = tien_dot(contract, idx)
    ky = _ky_cua_dot(inst)
    p = g.project

    sale = await _nguoi(db, p.sales_id)
    rate_sale = TY_LE_SALE_KHACH_RIENG if p.khach_rieng else TY_LE_SALE
    await g.them(sale, "hh_sale", rate_sale, tien, milestone="payment", idx=idx, ky=ky,
                 note="Khách riêng của sale" if p.khach_rieng else None)
    if sale:
        await g.them(await _truong_phong(db, "SALES"), "hh_tp_kd", TY_LE_TP_KD, tien,
                     milestone="payment", idx=idx, ky=ky)

    if loai_hop_dong(contract) == "thi_cong":
        designer = await _nguoi(db, p.designer_id)
        chu_tri = bool(designer and designer.role in VAI_TRO_TRUONG_NHOM.get("DESIGN", set()))
        tp_tk = await _truong_phong(db, "DESIGN")
        # Đợt 1–2 trả khi khách trả đợt 2; đợt 3+ trả khi nghiệm thu
        if idx <= IDX_DOT_2:
            ky_tk = ky if (len(dots) > IDX_DOT_2 and _da_thu(dots[IDX_DOT_2])) else None
        else:
            ky_tk = period_of(vn_today()) if contract.status == "completed" else None
        await g.them(designer, "hh_thiet_ke", TY_LE_THIET_KE_CHU_TRI if chu_tri else TY_LE_THIET_KE,
                     tien, milestone="payment", idx=idx, ky=ky_tk)
        await g.them(tp_tk if designer else None, "hh_tp_thiet_ke", TY_LE_TP_THIET_KE, tien, milestone="payment", idx=idx, ky=ky_tk)

        # Khách vừa trả đợt 2 → mở các dòng thiết kế đợt 1 đang chờ
        if idx == IDX_DOT_2:
            await _mo_cho_moc(db, contract, ky, lambda c: (c.installment_idx or 0) <= IDX_DOT_2)

    await g.bao()


async def khi_bo_thu_tien(db: AsyncSession, contract: Contract, idx: int) -> int:
    """Kế toán bỏ tích «đã thu» → gỡ dòng chưa duyệt của đợt đó. Dòng đã duyệt/
    đã trả giữ nguyên (kế toán xử lý tay, tránh tự đảo bảng lương đã chốt)."""
    rows = (await db.execute(
        select(Commission).where(
            Commission.contract_id == contract.id,
            Commission.installment_idx == idx,
            Commission.status.in_(("cho_moc", "pending")),
        )
    )).scalars().all()
    for c in rows:
        await db.delete(c)
    if idx == IDX_DOT_2:
        # Đợt 2 chưa thu nữa → dòng thiết kế đợt 1 trở lại «chờ mốc»
        lui = (await db.execute(
            select(Commission).where(
                Commission.contract_id == contract.id,
                Commission.type.in_(("hh_thiet_ke", "hh_tp_thiet_ke")),
                Commission.installment_idx <= IDX_DOT_2,
                Commission.status == "pending",
            )
        )).scalars().all()
        for c in lui:
            c.status, c.period = "cho_moc", None
    return len(rows)


async def _mo_cho_moc(db: AsyncSession, contract: Contract, ky: str, dieu_kien) -> None:
    rows = (await db.execute(
        select(Commission).where(
            Commission.contract_id == contract.id,
            Commission.status == "cho_moc",
        )
    )).scalars().all()
    for c in rows:
        if dieu_kien(c):
            c.status, c.period = "pending", ky


async def khi_ky_hop_dong(db: AsyncSession, contract: Contract) -> None:
    if loai_hop_dong(contract) != "thi_cong":
        return
    g = await _ghi_cho(db, contract)
    if not g:
        return
    gia_tri = float(contract.total_value or 0)
    ky = period_of(vn_today())
    thu_mua = await _nguoi(db, g.project.purchasing_id)
    # JD thu mua: «trả vào kỳ lương tiếp theo»
    await g.them(thu_mua, "hh_thu_mua", TY_LE_THU_MUA, gia_tri, milestone="signing", pct=0.5,
                 ky=_thang_sau(ky), note=await _ghi_chu_thu_viec(db, thu_mua))
    await g.them(await _truong_phong(db, "PURCHASING") if thu_mua else None, "hh_tp_bao_gia",
                 TY_LE_TP_BAO_GIA, gia_tri, milestone="signing", pct=0.5, ky=ky)
    await g.bao()


async def khi_nghiem_thu(db: AsyncSession, contract: Contract) -> None:
    if loai_hop_dong(contract) != "thi_cong":
        return
    g = await _ghi_cho(db, contract)
    if not g:
        return
    gia_tri = float(contract.total_value or 0)
    ky = period_of(vn_today())
    p = g.project

    thu_mua = await _nguoi(db, p.purchasing_id)
    await g.them(thu_mua, "hh_thu_mua", TY_LE_THU_MUA, gia_tri, milestone="handover", pct=0.5,
                 ky=_thang_sau(ky), note=await _ghi_chu_thu_viec(db, thu_mua))
    await g.them(await _truong_phong(db, "PURCHASING") if thu_mua else None, "hh_tp_bao_gia",
                 TY_LE_TP_BAO_GIA, gia_tri, milestone="handover", pct=0.5, ky=ky)
    giam_sat = await _nguoi(db, p.pm_id)
    await g.them(giam_sat, "hh_giam_sat", TY_LE_GIAM_SAT, gia_tri, milestone="handover", ky=ky)
    await g.them(await _truong_phong(db, "OPS") if giam_sat else None, "hh_tp_giam_sat", TY_LE_TP_GIAM_SAT, gia_tri,
                 milestone="handover", ky=ky)

    # Nghiệm thu → mở mọi dòng thiết kế còn «chờ mốc» (đợt 3 trở đi)
    await _mo_cho_moc(db, contract, ky, lambda c: True)
    await g.bao()
