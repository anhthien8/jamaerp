"""Giá nhập NCC theo mẫu (22/11/2026) — số liệu nền cho «Bảng giá chuẩn» của Giám đốc.

Mỗi mẫu: giá MỚI NHẤT của từng NCC, gộp hai nguồn:
- giá nhập Thu mua nạp thẳng cho mẫu (`GiaNhapMauVatTu`, không gắn dự án);
- báo giá NCC trong các dự án (`BaoGiaDongVatTu`) mà dòng phiếu đang mang đúng mẫu đó.

Toàn giá vốn + tên NCC: chỉ gọi từ endpoint đã gác `la_thu_mua` / admin.
"""

from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supplier import Supplier
from app.models.vat_tu import BaoGiaDongVatTu, DongPhieuVatTu, GiaNhapMauVatTu


def _naive(t: datetime) -> datetime:
    return t.astimezone(timezone.utc).replace(tzinfo=None) if t.tzinfo else t


async def gia_nhap_theo_mau(db: AsyncSession, mau_ids: Iterable[str]) -> dict[str, list[dict]]:
    """{mau_id: [giá mới nhất của từng NCC đang dùng]} — rẻ nhất đứng đầu. Hai query, không lặp theo mẫu.

    Mỗi giá: supplier_id, ncc_ten, hang (hạng NCC), gia, luc (naive UTC), nguon, cu (quá 60 ngày),
    ghi_chu, gia_nhap_id + created_by (chỉ có khi giá đến từ `GiaNhapMauVatTu`; báo giá dự án = None).
    """
    from app.api.vat_tu import gia_da_cu  # import trong hàm: api.vat_tu là tầng trên của services

    ids = list(set(mau_ids))
    if not ids:
        return {}
    ncc = (Supplier.id, Supplier.name, Supplier.hang)
    # Nối thẳng vào suppliers: báo giá gõ tay chưa gắn NCC (supplier_id rỗng) và NCC đã ngừng dùng tự rơi
    nhap = (await db.execute(
        select(GiaNhapMauVatTu.mau_id, *ncc, GiaNhapMauVatTu.gia, GiaNhapMauVatTu.created_at, GiaNhapMauVatTu.nguon,
               GiaNhapMauVatTu.ghi_chu, GiaNhapMauVatTu.id, GiaNhapMauVatTu.created_by)
        .join(Supplier, Supplier.id == GiaNhapMauVatTu.supplier_id)
        .where(GiaNhapMauVatTu.mau_id.in_(ids), Supplier.is_active.is_(True))
    )).all()
    bao = (await db.execute(
        select(DongPhieuVatTu.mau_id, *ncc, BaoGiaDongVatTu.gia, BaoGiaDongVatTu.created_at, BaoGiaDongVatTu.nguon,
               BaoGiaDongVatTu.ghi_chu, BaoGiaDongVatTu.duoc_chon, DongPhieuVatTu.gia_xac_nhan_luc)
        .join(DongPhieuVatTu, DongPhieuVatTu.id == BaoGiaDongVatTu.dong_id)
        .join(Supplier, Supplier.id == BaoGiaDongVatTu.supplier_id)
        .where(DongPhieuVatTu.mau_id.in_(ids), Supplier.is_active.is_(True))
    )).all()

    moi_nhat: dict[tuple[str, str], dict] = {}

    def xet(mau_id, sid, ten, hang, gia, luc, nguon, ghi_chu, gia_nhap_id=None, created_by=None) -> None:
        truoc = moi_nhat.get((mau_id, sid))
        if truoc is None or luc > truoc["luc"]:
            moi_nhat[(mau_id, sid)] = {
                "supplier_id": sid, "ncc_ten": ten, "hang": hang, "gia": gia, "luc": luc, "nguon": nguon,
                "cu": gia_da_cu(luc), "ghi_chu": ghi_chu, "gia_nhap_id": gia_nhap_id, "created_by": created_by,
            }

    for mau_id, sid, ten, hang, gia, luc, nguon, ghi_chu, gia_nhap_id, created_by in nhap:
        xet(mau_id, sid, ten, hang, gia, _naive(luc), nguon, ghi_chu, gia_nhap_id, created_by)
    for mau_id, sid, ten, hang, gia, luc, nguon, ghi_chu, duoc_chon, xac_nhan_luc in bao:
        luc = _naive(luc)
        # Dòng «chot» máy tự ghi lúc Thu mua gõ tay giá để chốt: gõ lại đúng giá đã nhớ thì bằng chứng
        # vẫn là ngày cũ (`gia_xac_nhan_luc` của dòng phiếu) — không tính là giá vừa hỏi lại hôm nay
        if nguon == "chot" and duoc_chon and xac_nhan_luc:
            luc = min(luc, _naive(xac_nhan_luc))
        xet(mau_id, sid, ten, hang, gia, luc, nguon, ghi_chu)

    kq: dict[str, list[dict]] = {}
    for (mau_id, _), g in moi_nhat.items():
        kq.setdefault(mau_id, []).append(g)
    for ds in kq.values():
        ds.sort(key=lambda g: (g["gia"], g["ncc_ten"]))
    return kq
