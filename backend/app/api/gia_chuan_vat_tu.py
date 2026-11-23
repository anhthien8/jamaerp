"""Bảng giá chuẩn vật tư (22/11/2026) — Giám đốc ấn định đơn giá bán của từng mẫu.

Giám đốc chốt «đơn giá là hằng số»: chỉ Giám đốc (role `admin`) đặt giá chuẩn
(`MauVatTu.gia_ban_co_dinh`); Thu mua nạp giá nhập của các NCC để Giám đốc có căn cứ.

Quyền: cả bảng là giá vốn + tên NCC + mức lời → chỉ `la_thu_mua` (admin hoặc bộ phận Thu mua).
KHÔNG dùng `xem_gia_von` — hàm đó cho cả trưởng phòng Kinh doanh / Thiết kế.
"""

import math
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.vat_tu import _phan_tram_nhom, ghi_doi_gia_chuan, gia_da_cu, yeu_cau_thu_mua
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.supplier import Supplier
from app.models.user import User
from app.models.vat_tu import GiaNhapMauVatTu, MauVatTu
from app.services.audit import log_action
from app.services.gia_nhap_vat_tu import gia_nhap_theo_mau
from app.services.ncc import BoNcc

router = APIRouter(prefix="/vat-tu/gia-chuan", tags=["vat-tu"])

HE_SO_MAC_DINH = 15.0  # nhóm chưa cài % lãi — cùng mặc định với lúc chốt giá


class GiaChuanIn(BaseModel):
    gia_chuan: float | None  # bắt buộc gửi; null = bỏ giá chuẩn


class GiaNhapIn(BaseModel):
    supplier_id: str | None = None
    ncc_ten: str | None = Field(default=None, max_length=255)
    gia: float
    ghi_chu: str | None = None


def _hop_le(gia: float) -> bool:
    return 0 < gia < math.inf  # loại luôn NaN / vô cực


def _muc(m: MauVatTu, pt: dict[str, float], gia_nhap: list[dict], user: User) -> dict:
    he_so = pt.get(m.nhom, HE_SO_MAC_DINH)
    gia_chuan = m.gia_ban_co_dinh if (m.gia_ban_co_dinh or 0) > 0 else None
    # Giá nhập mốc: giá vốn chốt gần nhất; mẫu chưa từng chốt thì lấy giá NCC thấp nhất đang có
    moc = m.gia_von_gan_nhat or (min(g["gia"] for g in gia_nhap) if gia_nhap else None)
    goi_y = round(moc * (1 + he_so / 100)) if moc else None
    return {
        "id": m.id, "ma": m.ma, "ten": m.ten, "hang": m.hang, "nhom": m.nhom, "don_vi": m.don_vi, "anh_url": m.anh_url,
        "gia_chuan": gia_chuan, "he_so": he_so,
        "gia_nhap": [{**g, "xoa_duoc": bool(g["gia_nhap_id"]) and (user.role == "admin" or g["created_by"] == user.id)}
                     for g in gia_nhap],
        "gia_nhap_gan_nhat": {
            "gia": m.gia_von_gan_nhat, "luc": m.gia_von_cap_nhat_luc, "ncc_ten": m.ncc_gan_nhat_ten,
            "cu": gia_da_cu(m.gia_von_cap_nhat_luc),
        } if m.gia_von_gan_nhat else None,
        "gia_tham_khao": m.gia_tham_khao, "gia_nhap_moc": moc, "gia_goi_y": goi_y,
        # % lời của giá chuẩn trên giá nhập mốc — cùng thước với hệ số nhóm
        "muc_loi_pct": round((gia_chuan / moc - 1) * 100, 1) if gia_chuan and moc else None,
        "chua_co": gia_chuan is None,
        "duoi_he_so": bool(gia_chuan and goi_y and gia_chuan < goi_y),
    }


async def _mau_hoac_404(db: AsyncSession, mau_id: str) -> MauVatTu:
    m = await db.get(MauVatTu, mau_id)
    if not m:
        raise HTTPException(404, "Không có mẫu này")
    return m


async def _muc_mot_mau(db: AsyncSession, m: MauVatTu, user: User) -> dict:
    return _muc(m, await _phan_tram_nhom(db), (await gia_nhap_theo_mau(db, [m.id])).get(m.id, []), user)


@router.get("")
async def bang_gia_chuan(
    loc: Literal["tat_ca", "chua_co", "duoi_he_so"] = "tat_ca", nhom: str | None = None, q: str | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
    user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db),
):
    stmt = select(MauVatTu).where(MauVatTu.is_active.is_(True))
    if nhom:
        stmt = stmt.where(MauVatTu.nhom == nhom)
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(MauVatTu.ma.ilike(like) | MauVatTu.ten.ilike(like) | MauVatTu.hang.ilike(like))
    maus = (await db.execute(stmt.order_by(MauVatTu.nhom, MauVatTu.hang, MauVatTu.ma, MauVatTu.id))).scalars().all()
    # Hai cờ lọc tính từ giá nhập của các NCC → phải tính cho cả danh mục rồi mới đếm và cắt trang
    pt = await _phan_tram_nhom(db)
    gia = await gia_nhap_theo_mau(db, [m.id for m in maus])
    tat_ca = [_muc(m, pt, gia.get(m.id, []), user) for m in maus]
    ds = tat_ca if loc == "tat_ca" else [x for x in tat_ca if x[loc]]
    dau = (page - 1) * page_size
    return {
        "items": ds[dau:dau + page_size], "total": len(ds), "page": page, "page_size": page_size,
        "tong": len(tat_ca), "so_chua_co": sum(x["chua_co"] for x in tat_ca),
        "so_duoi_he_so": sum(x["duoi_he_so"] for x in tat_ca),
        "co_the_sua_gia_chuan": user.role == "admin",
    }


@router.put("/{mau_id}")
async def dat_gia_chuan(mau_id: str, body: GiaChuanIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Đổi giá chuẩn của mẫu. Dòng phiếu CHƯA đặt hàng mà khách CHƯA đồng ý lấy ngay giá mới;
    dòng khách đã đồng ý và dòng đã đặt hàng giữ nguyên giá bán (`ghi_doi_gia_chuan`)."""
    if user.role != "admin":
        raise HTTPException(403, "Chỉ Giám đốc mới đặt giá chuẩn")
    m = await _mau_hoac_404(db, mau_id)
    moi = body.gia_chuan
    if moi is not None and not _hop_le(moi):
        raise HTTPException(400, "Giá chuẩn phải lớn hơn 0 — để trống nếu muốn bỏ giá chuẩn")
    cu = m.gia_ban_co_dinh
    m.gia_ban_co_dinh = moi
    await ghi_doi_gia_chuan(db, user, m, cu)  # giá không đổi thì không ghi gì
    await db.commit()
    return await _muc_mot_mau(db, m, user)


@router.post("/{mau_id}/gia-nhap", status_code=201)
async def them_gia_nhap(mau_id: str, body: GiaNhapIn, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    """Thu mua nạp giá nhập của một NCC cho mẫu — mỗi lần nạp là một dòng mới, giữ lịch sử."""
    m = await _mau_hoac_404(db, mau_id)
    if not _hop_le(body.gia):
        raise HTTPException(400, "Giá nhập phải lớn hơn 0")
    if body.supplier_id:
        s = await db.get(Supplier, body.supplier_id)
        if not s:
            raise HTTPException(404, "NCC không có trong Kho")
    else:
        s = await BoNcc(db).lay(body.ncc_ten)
        if not s:
            raise HTTPException(400, "Chọn hoặc gõ tên nhà cung cấp")
    if not s.is_active:
        # Bảng chỉ hiện NCC đang dùng — nhận giá của NCC đã ngừng thì giá nạp xong không thấy đâu
        raise HTTPException(400, f"NCC «{s.name}» đã ngừng dùng — bật «Dùng lại» ở mục Nhà cung cấp trước")
    db.add(GiaNhapMauVatTu(mau_id=m.id, supplier_id=s.id, gia=body.gia, nguon="tay",
                           ghi_chu=(body.ghi_chu or "").strip() or None, created_by=user.id))
    await db.commit()
    return await _muc_mot_mau(db, m, user)


@router.delete("/gia-nhap/{gia_nhap_id}", status_code=204)
async def xoa_gia_nhap(gia_nhap_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    g = await db.get(GiaNhapMauVatTu, gia_nhap_id)
    if not g:
        raise HTTPException(404, "Không có giá nhập này")
    if user.role != "admin" and g.created_by != user.id:
        raise HTTPException(403, "Chỉ người nạp giá này hoặc Giám đốc mới xoá được")
    await log_action(db, actor=user, action="vat_tu.xoa_gia_nhap", entity_type="gia_nhap_vat_tu", entity_id=g.id,
                     before={"mau_id": g.mau_id, "supplier_id": g.supplier_id, "gia": g.gia, "created_by": g.created_by})
    await db.delete(g)
    await db.commit()
