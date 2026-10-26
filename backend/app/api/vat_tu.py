"""Vật tư Đợt 1 (25/10/2026): danh mục mẫu · cài giá bán · phiếu chọn theo dự án · hỏi giá NCC.

Quyền (chốt với chủ dự án, không thêm ô ma trận):
- Xem giá vốn / NCC / báo giá / % lãi: admin, executive, bộ phận Thu mua, trưởng phòng.
  Sale & Thiết kế chỉ thấy giá bán. Hàm `xem_gia_von`.
- Chốt giá, ghi báo giá, bảng «Cần hỏi giá», cài % lãi: Thu mua (hoặc admin).
- Tạo/sửa dòng phiếu: ai vào được dự án (`require_project_access`).
Giá bán = max(giá vốn × (1 + % nhóm), giá cố định của mẫu) — tính ở server, không ai gõ.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.projects import require_project_access
from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import la_truong_phong
from app.models.notification import Notification
from app.models.project import Project
from app.models.supplier import Supplier
from app.models.user import User
from app.models.vat_tu import (
    NHAN_TRANG_THAI, TRANG_THAI_DONG, BaoGiaDongVatTu, DongPhieuVatTu, GiaNhomVatTu, MauVatTu,
)
from app.services import shopee_affiliate, vat_tu_sheet

router = APIRouter(prefix="/vat-tu", tags=["vat-tu"])

PHONG_THU_MUA = ("PURCHASING", "PROCUREMENT")


def _now():
    return datetime.now(timezone.utc)


def la_thu_mua(user: User) -> bool:
    return user.role == "admin" or (user.department or "").upper() in PHONG_THU_MUA


def xem_gia_von(user: User) -> bool:
    return user.role in ("admin", "executive") or la_thu_mua(user) or la_truong_phong(user)


def yeu_cau_thu_mua(user: User = Depends(get_current_user)) -> User:
    if not la_thu_mua(user):
        raise HTTPException(403, "Chỉ bộ phận Thu mua mới làm được việc này")
    return user


def yeu_cau_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Chỉ Admin mới cài giá bán")
    return user


async def quyen_du_an(project_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> User:
    """Thu mua lo vật tư cho MỌI dự án; người khác phải vào được dự án (PIC/trưởng phòng/có việc)."""
    if la_thu_mua(user):
        if not await db.get(Project, project_id):
            raise HTTPException(404, "Project not found")
        return user
    return await require_project_access(project_id, user, db)


def tinh_gia_ban(gia_von: float, phan_tram: float, gia_co_dinh: float | None) -> tuple[float, float | None]:
    """(giá bán, % áp dụng) — áp cái lãi hơn; % None nghĩa là dùng giá cố định."""
    theo_phan_tram = round(gia_von * (1 + phan_tram / 100))
    if gia_co_dinh and gia_co_dinh > theo_phan_tram:
        return float(gia_co_dinh), None
    return float(theo_phan_tram), phan_tram


# ── Schemas ────────────────────────────────────────────────────────────────

class MauIn(BaseModel):
    ma: str = Field(min_length=1, max_length=100)
    ten: str | None = None
    hang: str | None = None
    nhom: str = "Khác"
    be_mat: str | None = None
    don_vi: str = "m2"
    anh_url: str | None = Field(default=None, max_length=500)
    link_shopee: str | None = Field(default=None, max_length=500)
    ghi_chu: str | None = None
    tinh_trang: str | None = None
    gia_tham_khao: float | None = None
    gia_ban_co_dinh: float | None = None
    is_active: bool = True


class ImportSheetIn(BaseModel):
    url: str
    ghi_de: bool = False  # True: cập nhật mẫu trùng mã+nhóm; False: chỉ thêm mới


class GiaNhomIn(BaseModel):
    nhom: str
    phan_tram_lai: float = Field(ge=0, le=500)


class DongIn(BaseModel):
    phong: str = "Chung"
    hang_muc: str | None = None
    mau_id: str | None = None
    ma_tu_do: str | None = None
    so_luong: float = Field(default=1, gt=0)
    don_vi: str = "m2"
    ghi_chu: str | None = None


class DongPatch(BaseModel):
    phong: str | None = None
    hang_muc: str | None = None
    mau_id: str | None = None
    ma_tu_do: str | None = None
    so_luong: float | None = Field(default=None, gt=0)
    don_vi: str | None = None
    ghi_chu: str | None = None
    trang_thai: str | None = None
    mau_thay_the_id: str | None = None
    ma_thay_the: str | None = None
    ly_do_doi: str | None = None


class BaoGiaIn(BaseModel):
    supplier_id: str | None = None
    ncc_ten: str | None = None
    gia: float = Field(gt=0)
    con_hang: bool = True
    ngay_giao: str | None = None
    ghi_chu: str | None = None


class ChotIn(BaseModel):
    bao_gia_id: str | None = None   # chọn một báo giá đã ghi…
    gia_von: float | None = Field(default=None, gt=0)  # …hoặc gõ thẳng giá vốn
    supplier_id: str | None = None
    ncc_ten: str | None = None


class KhachDongYIn(BaseModel):
    ghi_chu: str | None = None


# ── Serializers ────────────────────────────────────────────────────────────

def _mau_dict(m: MauVatTu, thay_gia_von: bool) -> dict:
    d = {
        "id": m.id, "ma": m.ma, "ten": m.ten, "hang": m.hang, "nhom": m.nhom, "be_mat": m.be_mat,
        "don_vi": m.don_vi, "anh_url": m.anh_url, "link_shopee": m.link_shopee, "ghi_chu": m.ghi_chu, "tinh_trang": m.tinh_trang,
        "is_active": m.is_active, "gia_ban_co_dinh": m.gia_ban_co_dinh if thay_gia_von else None,
        "shopee_item_id": m.shopee_item_id, "shopee_ten": m.shopee_ten, "link_shopee_aff": m.link_shopee_aff,
        "gia_shopee": m.gia_shopee, "gia_shopee_luc": m.gia_shopee_luc,
    }
    if thay_gia_von:
        d.update({
            "gia_tham_khao": m.gia_tham_khao, "gia_von_gan_nhat": m.gia_von_gan_nhat,
            "gia_von_cap_nhat_luc": m.gia_von_cap_nhat_luc, "ncc_gan_nhat_ten": m.ncc_gan_nhat_ten,
        })
    return d


def _bao_gia_dict(b: BaoGiaDongVatTu, gia_shopee: float | None = None) -> dict:
    return {
        "id": b.id, "supplier_id": b.supplier_id, "ncc_ten": b.ncc_ten, "gia": b.gia, "con_hang": b.con_hang,
        "ngay_giao": b.ngay_giao, "ghi_chu": b.ghi_chu, "duoc_chon": b.duoc_chon, "created_at": b.created_at,
        "cao_hon_shopee": bool(gia_shopee and b.gia and b.gia > gia_shopee),
    }


def _dong_dict(d: DongPhieuVatTu, thay_gia_von: bool, mau: dict[str, MauVatTu], bao_gia: list[BaoGiaDongVatTu],
               ncc: dict[str, str], du_an: Project | None = None) -> dict:
    m = mau.get(d.mau_id or "")
    mt = mau.get(d.mau_thay_the_id or "")
    out = {
        "id": d.id, "project_id": d.project_id, "phong": d.phong, "hang_muc": d.hang_muc,
        "mau_id": d.mau_id, "ma": (m.ma if m else d.ma_tu_do), "hang": (m.hang if m else None),
        "nhom": (m.nhom if m else None), "anh_url": (m.anh_url if m else None), "ma_tu_do": d.ma_tu_do,
        "so_luong": d.so_luong, "don_vi": d.don_vi, "trang_thai": d.trang_thai,
        "trang_thai_nhan": NHAN_TRANG_THAI.get(d.trang_thai, d.trang_thai),
        "mau_thay_the_id": d.mau_thay_the_id, "ma_thay_the": (mt.ma if mt else d.ma_thay_the),
        "ly_do_doi": d.ly_do_doi, "gia_ban": d.gia_ban,
        "thanh_tien": (round(d.gia_ban * d.so_luong) if d.gia_ban else None),
        "chot_luc": d.chot_luc, "khach_dong_y_luc": d.khach_dong_y_luc, "khach_ghi_chu": d.khach_ghi_chu,
        "ghi_chu": d.ghi_chu, "thu_tu": d.thu_tu, "created_at": d.created_at, "updated_at": d.updated_at,
        "so_bao_gia": len(bao_gia),
        "gia_shopee": (m.gia_shopee if m else None), "link_shopee_aff": (m.link_shopee_aff if m else None),
    }
    if du_an is not None:
        out.update({"project_code": du_an.code, "project_name": du_an.name, "client_name": du_an.client_name})
    if thay_gia_von:
        out.update({
            "gia_von": d.gia_von, "ncc_id": d.ncc_id, "ncc_ten": ncc.get(d.ncc_id or ""),
            "phan_tram_ap_dung": d.phan_tram_ap_dung,
            "lai": (round((d.gia_ban - d.gia_von) * d.so_luong) if d.gia_ban and d.gia_von else None),
            "bao_gia": [_bao_gia_dict(b, m.gia_shopee if m else None) for b in bao_gia],
            "gia_von_gan_nhat": (m.gia_von_gan_nhat if m else None),
            "gia_tham_khao": (m.gia_tham_khao if m else None),
        })
    return out


async def _goi_dong(db: AsyncSession, ds: list[DongPhieuVatTu], user: User, kem_du_an=False) -> list[dict]:
    thay = xem_gia_von(user)
    ids_mau = {x for d in ds for x in (d.mau_id, d.mau_thay_the_id) if x}
    mau = {m.id: m for m in (await db.execute(select(MauVatTu).where(MauVatTu.id.in_(ids_mau)))).scalars()} if ids_mau else {}
    bg: dict[str, list[BaoGiaDongVatTu]] = {d.id: [] for d in ds}
    if ds and thay:
        for b in (await db.execute(
            select(BaoGiaDongVatTu).where(BaoGiaDongVatTu.dong_id.in_(list(bg))).order_by(BaoGiaDongVatTu.gia)
        )).scalars():
            bg[b.dong_id].append(b)
    ncc_ids = {d.ncc_id for d in ds if d.ncc_id}
    ncc = {s.id: s.name for s in (await db.execute(select(Supplier).where(Supplier.id.in_(ncc_ids)))).scalars()} if ncc_ids and thay else {}
    du_an: dict[str, Project] = {}
    if kem_du_an and ds:
        du_an = {p.id: p for p in (await db.execute(select(Project).where(Project.id.in_({d.project_id for d in ds})))).scalars()}
    return [_dong_dict(d, thay, mau, bg.get(d.id, []), ncc, du_an.get(d.project_id) if kem_du_an else None) for d in ds]


async def _phan_tram_nhom(db: AsyncSession) -> dict[str, float]:
    return {g.nhom: g.phan_tram_lai for g in (await db.execute(select(GiaNhomVatTu))).scalars()}


# ── Danh mục mẫu ───────────────────────────────────────────────────────────

@router.get("/mau")
async def danh_sach_mau(
    q: str | None = None, nhom: str | None = None, chi_dang_dung: bool = True,
    limit: int = Query(200, le=1000), offset: int = 0,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    stmt = select(MauVatTu)
    if chi_dang_dung:
        stmt = stmt.where(MauVatTu.is_active.is_(True))
    if nhom:
        stmt = stmt.where(MauVatTu.nhom == nhom)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(MauVatTu.ma.ilike(like) | MauVatTu.hang.ilike(like) | MauVatTu.ten.ilike(like))
    tong = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await db.execute(stmt.order_by(MauVatTu.nhom, MauVatTu.hang, MauVatTu.ma).limit(limit).offset(offset))).scalars().all()
    thay = xem_gia_von(user)
    return {"items": [_mau_dict(m, thay) for m in rows], "total": tong, "thay_gia_von": thay}


@router.get("/nhom")
async def danh_sach_nhom(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Nhóm + số mẫu; kèm % lãi nếu được xem giá vốn."""
    rows = (await db.execute(
        select(MauVatTu.nhom, func.count()).where(MauVatTu.is_active.is_(True)).group_by(MauVatTu.nhom).order_by(MauVatTu.nhom)
    )).all()
    pt = await _phan_tram_nhom(db) if xem_gia_von(user) else {}
    return [{"nhom": n, "so_mau": c, "phan_tram_lai": pt.get(n)} for n, c in rows]


@router.post("/mau", status_code=201)
async def tao_mau(body: MauIn, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    m = MauVatTu(**body.model_dump())
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return _mau_dict(m, True)


@router.put("/mau/{mau_id}")
async def sua_mau(mau_id: str, body: MauIn, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    m = await db.get(MauVatTu, mau_id)
    if not m:
        raise HTTPException(404, "Không có mẫu này")
    for k, v in body.model_dump().items():
        setattr(m, k, v)
    await db.commit()
    await db.refresh(m)
    return _mau_dict(m, True)


class AnhIn(BaseModel):
    data_base64: str  # JPG/PNG nén ở FE (canvas); server ép về JPG cạnh dài ≤800px


MAX_ANH_BYTES = 6 * 1024 * 1024


@router.post("/anh", status_code=201)
async def tai_anh_mau(body: AnhIn, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    """Tải ảnh mẫu từ máy → lưu Postgres → trả `anh_url` ký HMAC để gắn vào mẫu.
    Tách khỏi mẫu để tải được ngay khi đang điền form «Thêm mẫu» (mẫu chưa có id)."""
    import base64
    import binascii

    from app.models.vat_tu import AnhVatTu
    from app.services.media_gateway import MediaError, lam_anh_mau, url_anh_vat_tu

    try:
        raw = base64.b64decode(body.data_base64.split(",")[-1], validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(422, "Ảnh gửi lên không hợp lệ")
    if not raw:
        raise HTTPException(422, "Ảnh rỗng")
    if len(raw) > MAX_ANH_BYTES:
        raise HTTPException(413, "Ảnh quá lớn (tối đa 6MB)")
    try:
        jpg = lam_anh_mau(raw)
    except MediaError as exc:
        raise HTTPException(422, str(exc))
    anh = AnhVatTu(data=jpg, size_bytes=len(jpg), created_by=user.id)
    db.add(anh)
    await db.commit()
    return {"id": anh.id, "anh_url": url_anh_vat_tu(anh.id), "size_bytes": len(jpg)}


@router.post("/mau/import-sheet")
async def nhap_tu_sheet(body: ImportSheetIn, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    try:
        ds = await vat_tu_sheet.doc_sheet(body.url)
    except vat_tu_sheet.SheetError as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa: BLE001 — mạng, timeout…
        raise HTTPException(502, f"Không đọc được Google Sheet: {e}")
    co = {(m.ma.upper(), m.nhom): m for m in (await db.execute(select(MauVatTu))).scalars()}
    them = sua = 0
    for r in ds:
        khoa = (r["ma"].upper(), r["nhom"])
        if khoa in co:
            if body.ghi_de:
                for k, v in r.items():
                    if v is not None:
                        setattr(co[khoa], k, v)
                sua += 1
            continue
        m = MauVatTu(**r)
        db.add(m)
        co[khoa] = m
        them += 1
    # Nhóm mới chưa có % lãi → tạo dòng mặc định 15% để admin chỉnh một chỗ
    pt = await _phan_tram_nhom(db)
    for nhom in {r["nhom"] for r in ds} - set(pt):
        db.add(GiaNhomVatTu(nhom=nhom, phan_tram_lai=15.0, updated_by=user.id))
    await db.commit()
    return {"doc_duoc": len(ds), "them": them, "sua": sua}


# ── Cài giá bán ───────────────────────────────────────────────────────────

@router.get("/cai-gia")
async def xem_cai_gia(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not xem_gia_von(user):
        raise HTTPException(403, "Bạn không được xem cài đặt giá")
    rows = (await db.execute(select(GiaNhomVatTu).order_by(GiaNhomVatTu.nhom))).scalars().all()
    return [{"nhom": g.nhom, "phan_tram_lai": g.phan_tram_lai, "updated_at": g.updated_at} for g in rows]


@router.put("/cai-gia")
async def cai_gia(body: list[GiaNhomIn], user: User = Depends(yeu_cau_admin), db: AsyncSession = Depends(get_db)):
    for item in body:
        g = await db.get(GiaNhomVatTu, item.nhom)
        if g:
            g.phan_tram_lai = item.phan_tram_lai
            g.updated_by = user.id
        else:
            db.add(GiaNhomVatTu(nhom=item.nhom, phan_tram_lai=item.phan_tram_lai, updated_by=user.id))
    await db.commit()
    return {"ok": True, "so_nhom": len(body)}


# ── Phiếu chọn theo dự án ─────────────────────────────────────────────────

async def _dong_hoac_404(db: AsyncSession, dong_id: str) -> DongPhieuVatTu:
    d = await db.get(DongPhieuVatTu, dong_id)
    if not d:
        raise HTTPException(404, "Không có dòng vật tư này")
    return d


@router.get("/du-an/{project_id}/dong")
async def phieu_du_an(project_id: str, user: User = Depends(quyen_du_an), db: AsyncSession = Depends(get_db)):
    ds = (await db.execute(
        select(DongPhieuVatTu).where(DongPhieuVatTu.project_id == project_id)
        .order_by(DongPhieuVatTu.phong, DongPhieuVatTu.thu_tu, DongPhieuVatTu.created_at)
    )).scalars().all()
    items = await _goi_dong(db, ds, user)
    tong_ban = sum(i["thanh_tien"] or 0 for i in items)
    out = {"items": items, "tong_gia_ban": tong_ban, "thay_gia_von": xem_gia_von(user), "co_the_chot": la_thu_mua(user)}
    if out["thay_gia_von"]:
        out["tong_lai"] = sum(i.get("lai") or 0 for i in items)
    return out


@router.post("/du-an/{project_id}/dong", status_code=201)
async def them_dong(project_id: str, body: DongIn, user: User = Depends(quyen_du_an), db: AsyncSession = Depends(get_db)):
    if not body.mau_id and not (body.ma_tu_do or "").strip():
        raise HTTPException(400, "Chọn mẫu trong danh mục hoặc gõ mã vật tư")
    if body.mau_id and not await db.get(MauVatTu, body.mau_id):
        raise HTTPException(404, "Mẫu không có trong danh mục")
    thu_tu = (await db.execute(
        select(func.coalesce(func.max(DongPhieuVatTu.thu_tu), 0)).where(DongPhieuVatTu.project_id == project_id)
    )).scalar_one() + 1
    d = DongPhieuVatTu(project_id=project_id, created_by=user.id, thu_tu=thu_tu, **body.model_dump())
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return (await _goi_dong(db, [d], user))[0]


@router.patch("/dong/{dong_id}")
async def sua_dong(dong_id: str, body: DongPatch, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _dong_hoac_404(db, dong_id)
    await quyen_du_an(d.project_id, user, db)
    data = body.model_dump(exclude_unset=True)
    tt = data.get("trang_thai")
    if tt is not None:
        if tt not in TRANG_THAI_DONG:
            raise HTTPException(400, "Trạng thái không hợp lệ")
        # Bước thuộc Thu mua: hỏi NCC, báo hết hàng, đặt, giao. Chốt giá đi lối riêng.
        if tt in ("hoi_ncc", "het_hang", "da_dat", "da_giao") and not la_thu_mua(user):
            raise HTTPException(403, "Bước này do Thu mua cập nhật")
        if tt == "da_chot_gia":
            raise HTTPException(400, "Chốt giá bằng nút «Chốt giá»")
        if tt == "het_hang" and not (data.get("mau_thay_the_id") or data.get("ma_thay_the") or d.mau_thay_the_id or d.ma_thay_the):
            raise HTTPException(400, "Hết hàng thì phải kèm mẫu thay thế")
    for k, v in data.items():
        setattr(d, k, v)
    if tt == "het_hang":
        # Có mẫu thay → tự chuyển sang chờ khách duyệt lại khi thiết kế xem xong; Đợt 1 giữ het_hang
        pass
    await db.commit()
    await db.refresh(d)
    return (await _goi_dong(db, [d], user))[0]


@router.delete("/dong/{dong_id}", status_code=204)
async def xoa_dong(dong_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _dong_hoac_404(db, dong_id)
    await quyen_du_an(d.project_id, user, db)
    if d.trang_thai in ("da_chot_gia", "da_dat", "da_giao") and user.role != "admin":
        raise HTTPException(400, "Dòng đã chốt giá — chỉ Admin xoá được")
    for b in (await db.execute(select(BaoGiaDongVatTu).where(BaoGiaDongVatTu.dong_id == d.id))).scalars():
        await db.delete(b)
    await db.delete(d)
    await db.commit()


@router.post("/dong/{dong_id}/khach-dong-y")
async def khach_dong_y(dong_id: str, body: KhachDongYIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Đợt 1: nhân viên bấm thay khách (kèm ghi chú); Đợt 2 khách tự bấm trên portal."""
    d = await _dong_hoac_404(db, dong_id)
    await quyen_du_an(d.project_id, user, db)
    d.khach_dong_y_luc = _now()
    d.khach_ghi_chu = body.ghi_chu
    if d.trang_thai == "cho_khach_duyet_lai" or d.trang_thai == "het_hang":
        # Khách đồng ý mẫu thay → mẫu thay trở thành mẫu chính, quay lại hỏi giá
        if d.mau_thay_the_id or d.ma_thay_the:
            d.mau_id, d.ma_tu_do = d.mau_thay_the_id, (None if d.mau_thay_the_id else d.ma_thay_the)
            d.mau_thay_the_id = d.ma_thay_the = None
        d.trang_thai = "hoi_ncc"
    await db.commit()
    await db.refresh(d)
    return (await _goi_dong(db, [d], user))[0]


# ── Thu mua: cần hỏi giá, báo giá, chốt ───────────────────────────────────

@router.get("/can-hoi-gia")
async def can_hoi_gia(
    trang_thai: str | None = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    if not xem_gia_von(user):
        raise HTTPException(403, "Bảng này dành cho Thu mua / Ban giám đốc")
    tt = [trang_thai] if trang_thai else ["khach_chon", "hoi_ncc", "het_hang", "cho_khach_duyet_lai"]
    ds = (await db.execute(
        select(DongPhieuVatTu).where(DongPhieuVatTu.trang_thai.in_(tt)).order_by(DongPhieuVatTu.created_at)
    )).scalars().all()
    return {"items": await _goi_dong(db, ds, user, kem_du_an=True)}


@router.post("/dong/{dong_id}/bao-gia", status_code=201)
async def them_bao_gia(dong_id: str, body: BaoGiaIn, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    d = await _dong_hoac_404(db, dong_id)
    ten = (body.ncc_ten or "").strip()
    if body.supplier_id:
        s = await db.get(Supplier, body.supplier_id)
        if not s:
            raise HTTPException(404, "NCC không có trong Kho")
        ten = ten or s.name
    if not ten:
        raise HTTPException(400, "Cần tên NCC")
    b = BaoGiaDongVatTu(dong_id=d.id, supplier_id=body.supplier_id, ncc_ten=ten, gia=body.gia, con_hang=body.con_hang,
                        ngay_giao=body.ngay_giao, ghi_chu=body.ghi_chu, created_by=user.id)
    db.add(b)
    if d.trang_thai == "khach_chon":
        d.trang_thai = "hoi_ncc"
    await db.commit()
    await db.refresh(d)
    return (await _goi_dong(db, [d], user))[0]


@router.delete("/bao-gia/{bao_gia_id}", status_code=204)
async def xoa_bao_gia(bao_gia_id: str, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    b = await db.get(BaoGiaDongVatTu, bao_gia_id)
    if not b:
        raise HTTPException(404, "Không có báo giá này")
    if b.duoc_chon:
        raise HTTPException(400, "Báo giá đã chốt — không xoá")
    await db.delete(b)
    await db.commit()


@router.post("/dong/{dong_id}/chot")
async def chot_gia(dong_id: str, body: ChotIn, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    """Thu mua chốt giá vốn → server tính giá bán → ghi «giá gần nhất» về mẫu → báo PIC."""
    d = await _dong_hoac_404(db, dong_id)
    if d.trang_thai in ("da_dat", "da_giao", "huy"):
        raise HTTPException(400, "Dòng này không còn ở bước chốt giá")
    gia_von, supplier_id, ncc_ten = body.gia_von, body.supplier_id, (body.ncc_ten or "").strip() or None
    bao_gias = (await db.execute(select(BaoGiaDongVatTu).where(BaoGiaDongVatTu.dong_id == d.id))).scalars().all()
    if body.bao_gia_id:
        chon = next((b for b in bao_gias if b.id == body.bao_gia_id), None)
        if not chon:
            raise HTTPException(404, "Báo giá không thuộc dòng này")
        gia_von, supplier_id, ncc_ten = chon.gia, chon.supplier_id, chon.ncc_ten
        for b in bao_gias:
            b.duoc_chon = b.id == chon.id
    if not gia_von:
        raise HTTPException(400, "Cần chọn một báo giá hoặc gõ giá vốn")
    mau = await db.get(MauVatTu, d.mau_id) if d.mau_id else None
    nhom = mau.nhom if mau else "Khác"
    pt = (await _phan_tram_nhom(db)).get(nhom, 15.0)
    d.gia_ban, d.phan_tram_ap_dung = tinh_gia_ban(gia_von, pt, mau.gia_ban_co_dinh if mau else None)
    d.gia_von, d.ncc_id = gia_von, supplier_id
    d.chot_boi, d.chot_luc, d.trang_thai = user.id, _now(), "da_chot_gia"
    if mau:
        mau.gia_von_gan_nhat, mau.gia_von_cap_nhat_luc = gia_von, _now()
        mau.ncc_gan_nhat_id = supplier_id
        if ncc_ten:
            mau.ncc_gan_nhat_ten = ncc_ten
    # Báo người phụ trách dự án (thiết kế + KD) — họ chỉ thấy giá bán
    proj = await db.get(Project, d.project_id)
    if proj:
        ma = mau.ma if mau else (d.ma_tu_do or "")
        for uid in {proj.designer_id, proj.sales_id, proj.pm_id} - {None, user.id}:
            db.add(Notification(
                user_id=uid, type="vat_tu", title=f"Đã chốt giá vật tư · {proj.code}",
                body=f"{d.phong} · {ma}: {int(d.gia_ban):,}đ/{d.don_vi}".replace(",", "."),
                link=f"/vat-tu?project={proj.id}", ref_id=d.id,
            ))
    await db.commit()
    await db.refresh(d)
    return (await _goi_dong(db, [d], user))[0]


@router.get("/tong-quan")
async def tong_quan(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Số liệu cho đầu trang: số mẫu, số dòng theo trạng thái."""
    so_mau = (await db.execute(select(func.count()).select_from(MauVatTu).where(MauVatTu.is_active.is_(True)))).scalar_one()
    theo_tt = dict((await db.execute(
        select(DongPhieuVatTu.trang_thai, func.count()).group_by(DongPhieuVatTu.trang_thai)
    )).all())
    return {"so_mau": so_mau, "theo_trang_thai": theo_tt, "thay_gia_von": xem_gia_von(user), "la_thu_mua": la_thu_mua(user)}


# ── Bot Telegram nhập báo giá từ tệp (25/10/2026) ─────────────────────────
# Luồng: Thu mua gửi tệp cho bot → /bot/trich-bao-gia đọc + khớp mã với phiếu
# dự án → bot hiện bản xem trước → người bấm «Ghi» → /bot/ghi-bao-gia.
# Không bao giờ ghi thẳng từ tệp.

class TrichBaoGiaIn(BaseModel):
    project_id: str
    file_id: str
    file_name: str | None = None
    mime: str | None = None


class BaoGiaBotItem(BaseModel):
    dong_id: str
    ncc_ten: str = Field(min_length=1, max_length=150)
    gia: float = Field(gt=0)
    con_hang: bool = True
    ghi_chu: str | None = Field(default=None, max_length=300)


class GhiBaoGiaIn(BaseModel):
    items: list[BaoGiaBotItem] = Field(min_length=1, max_length=200)
    nguon: str | None = Field(default=None, max_length=200)  # «tệp baogia.xlsx»


async def _dong_cho_khop(db: AsyncSession, project_id: str) -> list[dict]:
    ds = (await db.execute(
        select(DongPhieuVatTu).where(DongPhieuVatTu.project_id == project_id).order_by(DongPhieuVatTu.thu_tu)
    )).scalars().all()
    ids = {d.mau_id for d in ds if d.mau_id}
    mau = {m.id: m for m in (await db.execute(select(MauVatTu).where(MauVatTu.id.in_(ids)))).scalars()} if ids else {}
    out = []
    for d in ds:
        m = mau.get(d.mau_id or "")
        out.append({
            "dong_id": d.id, "ma": (m.ma if m else d.ma_tu_do), "ma_phieu": (m.ma if m else d.ma_tu_do),
            "phong": d.phong, "so_luong": d.so_luong, "don_vi_phieu": d.don_vi, "trang_thai": d.trang_thai,
        })
    return out


@router.post("/bot/trich-bao-gia")
async def bot_trich_bao_gia(body: TrichBaoGiaIn, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    """Đọc tệp báo giá NCC (Excel/CSV/PDF/ảnh) từ Telegram → bản xem trước đã khớp
    mã với phiếu vật tư dự án. CHƯA ghi gì."""
    from app.services import vat_tu_bao_gia_tep as tep

    proj = await db.get(Project, body.project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    dong = await _dong_cho_khop(db, proj.id)
    if not dong:
        raise HTTPException(400, f"Dự án {proj.code} chưa có dòng vật tư nào — thêm phiếu chọn trên web trước")
    try:
        data = await tep.tai_tep_telegram(body.file_id)
        loai, chu = tep.tep_sang_chu(data, body.file_name, body.mime)
        kq = await tep.trich_tu_anh(data, body.mime) if loai == "image" else await tep.trich_tu_chu(chu)
    except tep.TepError as e:
        raise HTTPException(e.status, str(e))
    khop, khong = tep.khop_ma(kq["items"], dong)
    return {
        "project_code": proj.code, "project_name": proj.name, "ncc_ten": kq["ncc_ten"],
        "loai_tep": loai, "so_dong_phieu": len(dong), "so_doc_duoc": len(kq["items"]),
        "khop": khop, "khong_khop": khong[:30],
    }


@router.post("/bot/ghi-bao-gia", status_code=201)
async def bot_ghi_bao_gia(body: GhiBaoGiaIn, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    """Ghi hàng loạt báo giá đã được Thu mua xác nhận trên bot. Ghi chú ghi rõ nguồn tệp + người nhập."""
    ghi, loi = 0, []
    nguon = f"Nhập từ {body.nguon} bởi {user.full_name} (bot)" if body.nguon else f"Nhập qua bot bởi {user.full_name}"
    for it in body.items:
        d = await db.get(DongPhieuVatTu, it.dong_id)
        if not d:
            loi.append({"dong_id": it.dong_id, "loi": "Không có dòng này"})
            continue
        ghi_chu = f"{it.ghi_chu} · {nguon}" if it.ghi_chu else nguon
        db.add(BaoGiaDongVatTu(dong_id=d.id, ncc_ten=it.ncc_ten.strip(), gia=it.gia, con_hang=it.con_hang,
                               ghi_chu=ghi_chu[:500], created_by=user.id))
        if d.trang_thai == "khach_chon":
            d.trang_thai = "hoi_ncc"
        ghi += 1
    await db.commit()
    return {"ghi": ghi, "loi": loi}


# ── Shopee Affiliate: giá thị trường, cần thương lượng, gợi ý NCC (26/10/2026) ──

class ChonShopeeIn(BaseModel):
    item_id: str = Field(min_length=1, max_length=30)
    ten: str | None = Field(default=None, max_length=255)
    gia: float | None = Field(default=None, gt=0)
    link_aff: str | None = Field(default=None, max_length=500)


class LinkAffIn(BaseModel):
    url: str = Field(min_length=8, max_length=500)


async def _mau_hoac_404(db: AsyncSession, mau_id: str) -> MauVatTu:
    m = await db.get(MauVatTu, mau_id)
    if not m:
        raise HTTPException(404, "Không có mẫu này")
    return m


@router.get("/mau/{mau_id}/shopee")
async def tim_shopee_cho_mau(
    mau_id: str, q: str | None = None, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db),
):
    m = await _mau_hoac_404(db, mau_id)
    tu_khoa = (q or "").strip() or shopee_affiliate.tu_khoa_mau(m)
    try:
        items = await shopee_affiliate.tim_san_pham(db, tu_khoa)
    except shopee_affiliate.ShopeeError as exc:
        raise HTTPException(exc.status, str(exc))
    return {"tu_khoa": tu_khoa, "items": items}


@router.put("/mau/{mau_id}/shopee")
async def chon_shopee_cho_mau(
    mau_id: str, body: ChonShopeeIn, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db),
):
    m = await _mau_hoac_404(db, mau_id)
    m.shopee_item_id, m.shopee_ten, m.gia_shopee = body.item_id, body.ten, body.gia
    m.link_shopee_aff, m.gia_shopee_luc = body.link_aff, _now()
    await db.commit()
    await db.refresh(m)
    return _mau_dict(m, xem_gia_von(user))


@router.delete("/mau/{mau_id}/shopee")
async def bo_shopee_cho_mau(mau_id: str, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    m = await _mau_hoac_404(db, mau_id)
    m.shopee_item_id = m.shopee_ten = m.link_shopee_aff = None
    m.gia_shopee = m.gia_shopee_luc = None
    await db.commit()
    await db.refresh(m)
    return _mau_dict(m, xem_gia_von(user))


@router.post("/mau/{mau_id}/shopee/link")
async def doi_link_aff(mau_id: str, body: LinkAffIn, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    """Link Shopee dán tay → link affiliate của JAMA."""
    m = await _mau_hoac_404(db, mau_id)
    url = body.url.strip()
    if "shopee" not in url.lower() and "shp.ee" not in url.lower():
        raise HTTPException(400, "Đây không phải link Shopee")
    try:
        m.link_shopee_aff = await shopee_affiliate.link_aff(db, url)
    except shopee_affiliate.ShopeeError as exc:
        raise HTTPException(exc.status, str(exc))
    m.link_shopee = m.link_shopee or url
    await db.commit()
    await db.refresh(m)
    return _mau_dict(m, xem_gia_von(user))


@router.get("/can-thuong-luong")
async def can_thuong_luong(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Báo giá NCC cao hơn giá Shopee của cùng mẫu — danh sách để đi thương lượng."""
    if not xem_gia_von(user):
        raise HTTPException(403, "Bảng này dành cho Thu mua / Ban giám đốc")
    rows = (await db.execute(
        select(BaoGiaDongVatTu, MauVatTu, DongPhieuVatTu.project_id)
        .join(DongPhieuVatTu, DongPhieuVatTu.id == BaoGiaDongVatTu.dong_id)
        .join(MauVatTu, MauVatTu.id == DongPhieuVatTu.mau_id)
        .where(MauVatTu.gia_shopee.is_not(None), BaoGiaDongVatTu.gia > MauVatTu.gia_shopee,
               DongPhieuVatTu.trang_thai != "huy")
        .order_by(BaoGiaDongVatTu.created_at.desc()).limit(300)
    )).all()
    pids = {pid for _, _, pid in rows}
    du_an = {p.id: p.code for p in (await db.execute(select(Project).where(Project.id.in_(pids)))).scalars()} if pids else {}
    items = [{
        "bao_gia_id": b.id, "dong_id": b.dong_id, "ncc_ten": b.ncc_ten, "supplier_id": b.supplier_id,
        "gia_ncc": b.gia, "gia_shopee": m.gia_shopee, "chenh": round(b.gia - m.gia_shopee),
        "chenh_pct": round((b.gia / m.gia_shopee - 1) * 100, 1), "mau_id": m.id, "ma": m.ma, "hang": m.hang,
        "don_vi": m.don_vi, "link_shopee_aff": m.link_shopee_aff, "project_code": du_an.get(pid),
        "duoc_chon": b.duoc_chon, "created_at": b.created_at,
    } for b, m, pid in rows]
    items.sort(key=lambda x: -x["chenh_pct"])
    return {"items": items}


@router.get("/mau/{mau_id}/goi-y-ncc")
async def goi_y_ncc(mau_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Xếp NCC cho một mẫu: còn hàng → giá sau chiết khấu thấp nhất → tổng tiền JAMA đã mua của NCC cao nhất."""
    if not xem_gia_von(user):
        raise HTTPException(403, "Chỉ Thu mua / Ban giám đốc xem được giá NCC")
    m = await _mau_hoac_404(db, mau_id)
    bgs = (await db.execute(
        select(BaoGiaDongVatTu).join(DongPhieuVatTu, DongPhieuVatTu.id == BaoGiaDongVatTu.dong_id)
        .where(DongPhieuVatTu.mau_id == mau_id).order_by(BaoGiaDongVatTu.created_at.desc())
    )).scalars().all()
    moi_nhat: dict[str, BaoGiaDongVatTu] = {}  # mỗi NCC lấy báo giá mới nhất
    for b in bgs:
        moi_nhat.setdefault(b.supplier_id or f"ten:{(b.ncc_ten or '').strip().lower()}", b)
    sids = [b.supplier_id for b in moi_nhat.values() if b.supplier_id]
    ncc = {s.id: s for s in (await db.execute(select(Supplier).where(Supplier.id.in_(sids)))).scalars()} if sids else {}
    da_mua = dict((await db.execute(
        select(DongPhieuVatTu.ncc_id, func.sum(DongPhieuVatTu.gia_von * DongPhieuVatTu.so_luong))
        .where(DongPhieuVatTu.ncc_id.in_(sids), DongPhieuVatTu.gia_von.is_not(None), DongPhieuVatTu.trang_thai != "huy")
        .group_by(DongPhieuVatTu.ncc_id)
    )).all()) if sids else {}
    items = []
    for b in moi_nhat.values():
        s = ncc.get(b.supplier_id or "")
        ck = float(s.chiet_khau_pct or 0) if s else 0.0
        sau_ck = round(b.gia * (1 - ck / 100))
        items.append({
            "supplier_id": b.supplier_id, "ncc_ten": s.name if s else b.ncc_ten, "gia": b.gia, "chiet_khau_pct": ck,
            "gia_sau_ck": sau_ck, "da_mua": round(float(da_mua.get(b.supplier_id, 0) or 0)),
            "con_hang": b.con_hang, "bao_gia_luc": b.created_at,
            "cao_hon_shopee": bool(m.gia_shopee and sau_ck > m.gia_shopee),
        })
    items.sort(key=lambda x: (not x["con_hang"], x["gia_sau_ck"], -x["da_mua"]))
    return {"gia_shopee": m.gia_shopee, "link_shopee_aff": m.link_shopee_aff, "items": items,
            "goi_y": items[0] if items else None}
