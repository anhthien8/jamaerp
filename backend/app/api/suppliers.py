"""Suppliers API — NCC management & price comparison."""

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.chuan_hoa_unicode import nfc
from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.permissions import quyen_hieu_luc
from app.middleware.permissions import yeu_cau
from app.models.user import User
from app.models.supplier import HANG_NCC, Supplier, SupplierQuote, PriceComparison
from app.models.vat_tu import BaoGiaDongVatTu, DongPhieuVatTu, GiaNhapMauVatTu, MauVatTu
from app.services import ncc
from app.services.audit import log_action
from app.schemas.supplier import (
    SupplierCreate,
    SupplierUpdate,
    SupplierResponse,
    SupplierQuoteCreate,
    SupplierQuoteResponse,
    CompareRequest,
)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def _escape_like(term: str) -> str:
    return term.replace("%", "\\%").replace("_", "\\_")


async def require_supplier_write(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Gate sửa Nhà cung cấp qua ô «Sửa Nhà cung cấp» trong ma trận Phân quyền.

    Bản cũ hardcode `role in (admin, supervisor)`. Đo prod 22/09: chỉ 6 người
    sửa được (4 admin + 2 supervisor), còn TOÀN BỘ 8 nhân sự Thu mua
    (thu_mua/du_toan/dutoan_thumua_leader) thì không — dù cập nhật nhà cung cấp
    đúng là việc của họ. Không có ô nào trong ma trận nên admin cũng chẳng cấp
    được. Nay có ô, cấp/thu bằng trang Phân quyền.
    """
    perms = await quyen_hieu_luc(current_user, db)
    if not perms.get("canEditSuppliers"):
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền «Sửa Nhà cung cấp» — xem trang Phân quyền",
        )
    return current_user


# ---------------------------------------------------------------------------
# Dữ liệu gốc NCC sạch (22/11/2026): một NCC một dòng — chặn trùng khi tạo/đổi tên, gộp NCC trùng
# ---------------------------------------------------------------------------

HANG_CHUA_XEP = "chua_xep"  # giá trị lọc `hang` cho NCC chưa xếp hạng
# Cột NOT NULL: form gửi null (ô để trống) thì giữ giá trị đang lưu, không để DB báo lỗi 500
_COT_BAT_BUOC = ("name", "category", "rating", "chiet_khau_pct", "is_active")

# MỌI cột giữ id NCC, kèm cột chép tên NCC (nếu có). Thêm cột mới trỏ tới suppliers.id thì
# thêm vào đây — test_ncc_gop_trung soi metadata, thiếu là đỏ.
_COT_NCC = (
    (DongPhieuVatTu.ncc_id, None),
    (MauVatTu.ncc_gan_nhat_id, MauVatTu.ncc_gan_nhat_ten),
    (BaoGiaDongVatTu.supplier_id, BaoGiaDongVatTu.ncc_ten),
    (GiaNhapMauVatTu.supplier_id, None),
    (SupplierQuote.supplier_id, None),
    (PriceComparison.best_supplier_id, None),
)
# Khi gộp: ô còn trống ở NCC giữ lại thì lấy của NCC bị gộp. `_COI_NHU_TRONG` = giá trị mặc định
# máy tự điền, không phải thông tin người dùng nhập (ghi chú: của BoNcc và của migration a17).
_COT_BU = ("contact_name", "phone", "zalo", "email", "address", "region", "category",
           "ma_so_thue", "ten_cong_ty", "chiet_khau_pct", "notes", "hang")
_COI_NHU_TRONG = {
    "category": ("general",),
    "notes": (ncc.GHI_CHU_TU_TAO, "Tự tạo từ tên NCC ở Vật tư — bổ sung liên hệ sau"),
}


def _don_du_lieu(d: dict, mst_cu: str | None = None) -> dict:
    """Dọn chữ người dùng gõ trước khi ghi: tên gọn khoảng trắng, MST về dạng chuẩn, hạng hợp lệ."""
    if d.get("name") is not None:
        d["name"] = re.sub(r"\s+", " ", d["name"]).strip()
        if not d["name"]:
            raise HTTPException(400, "Cần tên nhà cung cấp")
    if "ma_so_thue" in d:
        tho = (d["ma_so_thue"] or "").strip()
        d["ma_so_thue"] = ncc.chuan_mst(tho) if tho else None
        if tho and not d["ma_so_thue"]:
            # MST cũ sai dạng mà form gửi lại nguyên văn → giữ, không chặn việc sửa các ô khác
            if tho != mst_cu:
                raise HTTPException(400, "Mã số thuế gồm 10 số (chi nhánh: 10 số-3 số)")
            d["ma_so_thue"] = tho
    if "hang" in d:
        d["hang"] = d["hang"] or None
        if d["hang"] and d["hang"] not in HANG_NCC:
            raise HTTPException(400, "Hạng nhà cung cấp không hợp lệ")
    return d


async def _tro_ve(db: AsyncSession, cot, cot_ten, tu_id: str, s: Supplier) -> int:
    """Mọi dòng đang giữ NCC `tu_id` ở cột `cot` → trỏ về `s`, chép lại tên `s` nếu bảng có cột tên."""
    bang = cot.class_
    gia_tri = {cot.key: s.id}
    if cot_ten is not None:
        gia_tri[cot_ten.key] = s.name
    if hasattr(bang, "updated_at"):
        # Giữ nguyên updated_at (không để onupdate tự nhảy): «Dữ liệu chung» đọc
        # dong_phieu_vat_tu.updated_at làm dấu vết Thu mua cập nhật dự án — sửa/gộp NCC không phải việc đó
        gia_tri["updated_at"] = bang.updated_at
    return (await db.execute(update(bang).where(cot == tu_id).values(gia_tri))).rowcount


def _mst_gon(s: str | None) -> str | None:
    """MST về dạng chuẩn để so với nhau; MST cũ sai dạng thì so nguyên văn."""
    return ncc.chuan_mst(s) or s or None


def _trung_mst(mst: str | None, mst_co: str | None) -> bool:
    return bool(mst) and _mst_gon(mst) == _mst_gon(mst_co)


def _trung_ten(ten: str | None, mst: str | None, ten_co: str, mst_co: str | None) -> bool:
    """Cùng khoá tên (đã bỏ chữ «Công ty TNHH…»). Hai MST chứng tỏ là hai pháp nhân khác nhau thì KHÔNG
    trùng («Công ty TNHH An Phát» ≠ «Công ty CP An Phát») — trừ khi tên y hệt: hai NCC cùng tên thì
    không ai phân biệt được ở ô gợi ý."""
    khoa = ncc.khoa_ncc(ten)
    return bool(khoa) and khoa == ncc.khoa_ncc(ten_co) and (
        ncc.chuan_ten(ten) == ncc.chuan_ten(ten_co) or not ncc.khac_phap_nhan(mst, mst_co))


async def _chan_trung(db: AsyncSession, *, ten: str | None, mst: str | None, cu: Supplier | None = None) -> None:
    """Trùng MST hoặc trùng tên với NCC khác → 409 nêu đích danh NCC đang có.

    `cu` = NCC đang sửa (giá trị TRƯỚC khi ghi): chỉ chặn cái trùng do lần sửa này gây ra — NCC lỡ trùng
    từ trước 22/11 vẫn sửa được ô khác (rồi BGĐ gộp).
    """
    if not ncc.khoa_ncc(ten) and not mst:
        return
    rows = (await db.execute(
        select(Supplier.id, Supplier.name, Supplier.ma_so_thue, Supplier.is_active)
        # NCC đang dùng trước: còn NCC đang dùng cùng tên thì không nêu cái đã «Ngừng dùng» rồi mời «mở để dùng lại»
        .order_by(Supplier.is_active.desc(), Supplier.created_at, Supplier.id)
    )).all()
    for sid, ten_co, mst_co, dang_dung in rows:
        if cu is not None and sid == cu.id:
            continue
        if _trung_mst(mst, mst_co) and not (cu is not None and _trung_mst(cu.ma_so_thue, mst_co)):
            loi = f"Mã số thuế {mst} trùng nhà cung cấp «{ten_co}» đã có"
        elif _trung_ten(ten, mst, ten_co, mst_co) and not (
                cu is not None and _trung_ten(cu.name, cu.ma_so_thue, ten_co, mst_co)):
            loi = f"Tên này trùng nhà cung cấp «{ten_co}» đã có"
        else:
            continue
        if not dang_dung:
            loi += " (đang ngừng dùng)"
        # detail dạng {message, …} — frontend ApiError lấy `message` làm câu báo lỗi
        raise HTTPException(status_code=409, detail={
            "message": loi, "supplier_id": sid, "supplier_name": ten_co, "is_active": dang_dung,
        })


# ---------------------------------------------------------------------------
# Supplier CRUD
# ---------------------------------------------------------------------------


@router.get("")
async def list_suppliers(
    search: str | None = None,
    category: str | None = None,
    region: str | None = None,
    hang: str | None = None,
    is_active: bool | None = None,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    # Danh bạ NCC + giá mua vào là bí mật kinh doanh — gác theo ô «Xem Kho»
    # (trang NCC nằm trong mảng kho/thu mua). Trước 13/08/2026 chỉ cần đăng nhập.
    current_user: User = Depends(yeu_cau("canViewInventory")),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """Danh sách NCC đang dùng. NCC đã «Ngừng dùng» chỉ hiện khi `include_inactive=true`
    (hoặc lọc đích danh `is_active=false`). `hang` = khoá HANG_NCC, hoặc `chua_xep`."""
    # Thêm id: tên trùng nhau mà chỉ xếp theo tên thì Postgres có thể trả một NCC ở cả hai trang, bỏ sót NCC kia
    q = select(Supplier).order_by(Supplier.name, Supplier.id)
    if search:
        escaped = _escape_like(search)
        q = q.where(
            Supplier.name.ilike(f"%{escaped}%", escape="\\")
            | Supplier.contact_name.ilike(f"%{escaped}%", escape="\\")
            | Supplier.ma_so_thue.ilike(f"%{escaped}%", escape="\\")
            | Supplier.ten_cong_ty.ilike(f"%{escaped}%", escape="\\")
        )
    if category:
        q = q.where(Supplier.category == category)
    if region:
        q = q.where(Supplier.region == region)
    if hang == HANG_CHUA_XEP:
        q = q.where(Supplier.hang.is_(None))
    elif hang:
        q = q.where(Supplier.hang == hang)
    if is_active is not None:
        q = q.where(Supplier.is_active == is_active)
    elif not include_inactive:
        q = q.where(Supplier.is_active.is_(True))

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    suppliers = result.scalars().all()

    return {
        "items": [SupplierResponse.model_validate(s) for s in suppliers],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.post("", response_model=SupplierResponse)
async def create_supplier(
    data: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_supplier_write),
):
    """Create a new supplier."""
    d = _don_du_lieu(data.model_dump())
    await _chan_trung(db, ten=d["name"], mst=d["ma_so_thue"])
    supplier = Supplier(**d)
    db.add(supplier)
    await db.flush()
    return SupplierResponse.model_validate(supplier)


@router.get("/tra-mst/{mst}")
async def tra_ma_so_thue(mst: str, current_user: User = Depends(get_current_user)):
    """Tra MST (dữ liệu Cục Thuế qua VietQR) → tên công ty + địa chỉ để điền form NCC."""
    if not ncc.chuan_mst(mst):
        raise HTTPException(400, "Mã số thuế gồm 10 số (chi nhánh: 10 số-3 số)")
    kq = await ncc.tra_mst(mst)
    if not kq:
        raise HTTPException(404, "Không tìm thấy mã số thuế này — kiểm tra lại hoặc nhập tay")
    return kq


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(yeu_cau("canViewInventory")),
):
    """Get supplier detail."""
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Nhà cung cấp không tồn tại")
    return SupplierResponse.model_validate(supplier)


@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: str,
    data: SupplierUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_supplier_write),
):
    """Update supplier."""
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Nhà cung cấp không tồn tại")

    thay = _don_du_lieu(data.model_dump(exclude_unset=True), mst_cu=supplier.ma_so_thue)
    ten = thay.get("name")
    if ten or "ma_so_thue" in thay:
        # Tên và MST SAU khi sửa (ô không gửi = cái đang lưu): bỏ MST đi là hết bằng chứng «hai pháp nhân khác nhau»
        await _chan_trung(db, ten=ten or supplier.name, mst=thay.get("ma_so_thue", supplier.ma_so_thue), cu=supplier)
    doi_ten = bool(ten) and ten != supplier.name
    for k, v in thay.items():
        if v is None and k in _COT_BAT_BUOC:
            continue
        setattr(supplier, k, v)
    supplier.updated_at = datetime.now(timezone.utc)
    await db.flush()
    if doi_ten:
        # Mẫu và báo giá chép tên NCC; form sửa mẫu gửi lại tên chép đó cho BoNcc — để tên cũ
        # nằm lại thì lần sửa mẫu kế tiếp sinh ra một NCC mới mang tên cũ.
        for cot, cot_ten in _COT_NCC:
            if cot_ten is not None:
                await _tro_ve(db, cot, cot_ten, supplier.id, supplier)
    return SupplierResponse.model_validate(supplier)


@router.post("/{supplier_id}/gop/{dich_id}")
async def gop_ncc(
    supplier_id: str,
    dich_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Gộp NCC trùng: chuyển mọi thứ của `supplier_id` sang `dich_id` rồi XOÁ `supplier_id`.

    Không hoàn tác được — nhật ký (audit) giữ đủ để dựng lại tay nếu gộp nhầm: bản chụp NCC bị xoá,
    NCC giữ lại trước khi được bù ô trống, id từng dòng đã chuyển.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ Ban giám đốc được gộp nhà cung cấp")
    if supplier_id == dich_id:
        raise HTTPException(status_code=400, detail="Chọn một nhà cung cấp KHÁC để gộp vào")
    nguon = await db.get(Supplier, supplier_id)
    dich = await db.get(Supplier, dich_id)
    if not nguon or not dich:
        raise HTTPException(status_code=404, detail="Nhà cung cấp không tồn tại")

    truoc = SupplierResponse.model_validate(nguon).model_dump(mode="json")
    dich_truoc = SupplierResponse.model_validate(dich).model_dump(mode="json")
    # Tên công ty là tên THEO mã số thuế: NCC giữ lại đã có MST khác (trụ sở ≠ chi nhánh «-001»,
    # hai công ty cùng thương hiệu) thì không nhận tên pháp lý của nguồn
    khac_mst = bool(dich.ma_so_thue) and _mst_gon(dich.ma_so_thue) != _mst_gon(nguon.ma_so_thue)
    for cot in _COT_BU:
        if cot == "ten_cong_ty" and khac_mst:
            continue
        co, cua_nguon = getattr(dich, cot), getattr(nguon, cot)
        trong = _COI_NHU_TRONG.get(cot, ())
        if (not co or co in trong) and cua_nguon and cua_nguon not in trong:
            setattr(dich, cot, cua_nguon)

    # Sau khi chuyển, dòng của nguồn lẫn với dòng của NCC giữ lại → ghi id từng dòng trước khi chuyển
    id_da_chuyen: dict[str, list[str]] = {}
    for cot, cot_ten in _COT_NCC:
        bang = cot.class_
        id_da_chuyen[bang.__tablename__] = list(
            (await db.execute(select(bang.id).where(cot == nguon.id).order_by(bang.id))).scalars())
        await _tro_ve(db, cot, cot_ten, nguon.id, dich)
    da_chuyen = {bang: len(ids) for bang, ids in id_da_chuyen.items()}
    # Không có bảng tên gọi khác: tên nguồn khác khoá tên giữ lại («Hiep Phat» → «Hiệp Phát») thì lần gõ /
    # nhập sheet / tệp báo giá sau vẫn mang tên cũ sẽ TẠO LẠI NCC vừa gộp — báo để BGĐ sửa tên ở nguồn
    ten_khac_khoa = ncc.khoa_ncc(nguon.name) != ncc.khoa_ncc(dich.name)
    await db.delete(nguon)
    await log_action(
        db, actor=current_user, action="supplier.gop", entity_type="supplier", entity_id=dich.id,
        before=truoc,
        after={"gop_vao": dich.name, "da_chuyen": da_chuyen, "id_da_chuyen": id_da_chuyen,
               "dich_truoc_khi_bu": dich_truoc},
        note=f"Gộp «{nguon.name}» vào «{dich.name}»"[:500],
    )
    return {"supplier": SupplierResponse.model_validate(dich), "da_chuyen": da_chuyen,
            "ten_khac_khoa": ten_khac_khoa}


# ---------------------------------------------------------------------------
# Supplier Quotes
# ---------------------------------------------------------------------------


@router.get("/{supplier_id}/quotes")
async def list_supplier_quotes(
    supplier_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(yeu_cau("canViewInventory")),
):
    """List all price quotes for a supplier."""
    # Verify supplier exists
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Nhà cung cấp không tồn tại")

    q = (
        select(SupplierQuote)
        .where(SupplierQuote.supplier_id == supplier_id)
        .order_by(desc(SupplierQuote.quote_date))
    )
    result = await db.execute(q)
    quotes = result.scalars().all()
    return {
        "items": [SupplierQuoteResponse.model_validate(q) for q in quotes],
        "total": len(quotes),
    }


@router.post("/{supplier_id}/quotes", response_model=SupplierQuoteResponse)
async def create_supplier_quote(
    supplier_id: str,
    data: SupplierQuoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_supplier_write),
):
    """Add a price quote for a supplier."""
    # Verify supplier exists
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Nhà cung cấp không tồn tại")

    quote = SupplierQuote(supplier_id=supplier_id, **data.model_dump())
    db.add(quote)
    await db.flush()
    return SupplierQuoteResponse.model_validate(quote)


# ---------------------------------------------------------------------------
# Price Comparison
# ---------------------------------------------------------------------------


@router.post("/compare")
async def compare_prices(
    data: CompareRequest,
    db: AsyncSession = Depends(get_db),
    # POST nhưng thuần đọc (so giá, không ghi gì) — cùng cửa «Xem Kho».
    current_user: User = Depends(yeu_cau("canViewInventory")),
):
    """Compare prices across suppliers for a list of materials."""
    results = []
    for mat_name in data.materials:
        # Get latest quotes for each supplier for this material
        q = (
            select(SupplierQuote, Supplier.name.label("supplier_name"))
            .join(Supplier, SupplierQuote.supplier_id == Supplier.id)
            # NFC (21/11/2026): tên vật tư trong body gõ dạng tổ hợp vẫn khớp báo giá đã lưu
            .where(SupplierQuote.material_name == nfc(mat_name))
            .where(Supplier.is_active == True)
            .order_by(desc(SupplierQuote.quote_date))
        )
        result = await db.execute(q)
        rows = result.all()

        # Deduplicate: keep only the latest quote per supplier
        seen_suppliers: dict[str, tuple[SupplierQuote, str]] = {}
        for quote, supplier_name in rows:
            if quote.supplier_id not in seen_suppliers:
                seen_suppliers[quote.supplier_id] = (quote, supplier_name)

        quotes = []
        best_price = None
        best_supplier_id = None
        best_supplier_name = None

        for sid, (quote, sname) in seen_suppliers.items():
            quotes.append({
                "supplier_id": sid,
                "supplier_name": sname,
                "unit_price": quote.unit_price,
                "unit": quote.unit,
                "min_quantity": quote.min_quantity,
                "lead_time_days": quote.lead_time_days,
                "quote_date": quote.quote_date.isoformat(),
            })
            if best_price is None or quote.unit_price < best_price:
                best_price = quote.unit_price
                best_supplier_id = sid
                best_supplier_name = sname

        # Sort by price ascending
        quotes.sort(key=lambda x: x["unit_price"])

        results.append({
            "material_name": mat_name,
            "quote_count": len(quotes),
            "best_supplier_id": best_supplier_id,
            "best_supplier_name": best_supplier_name,
            "best_price": best_price,
            "quotes": quotes,
        })

    return {"comparisons": results}


@router.get("/price-history/{material_name:path}")
async def price_history(
    material_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(yeu_cau("canViewInventory")),
):
    """Get price history for a material across all suppliers."""
    q = (
        select(SupplierQuote, Supplier.name.label("supplier_name"))
        .join(Supplier, SupplierQuote.supplier_id == Supplier.id)
        # Path không qua middleware query string → NFC tại chỗ (21/11/2026)
        .where(SupplierQuote.material_name == nfc(material_name))
        .order_by(desc(SupplierQuote.quote_date))
    )
    result = await db.execute(q)
    rows = result.all()

    history = []
    for quote, supplier_name in rows:
        history.append({
            "id": quote.id,
            "supplier_id": quote.supplier_id,
            "supplier_name": supplier_name,
            "unit_price": quote.unit_price,
            "unit": quote.unit,
            "min_quantity": quote.min_quantity,
            "lead_time_days": quote.lead_time_days,
            "quote_date": quote.quote_date.isoformat(),
            "notes": quote.notes,
        })

    return {
        "material_name": material_name,
        "total": len(history),
        "history": history,
    }
