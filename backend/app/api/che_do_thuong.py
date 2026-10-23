"""Chế độ thưởng (23/10/2026) — Cài đặt › Nhân sự › Chế độ thưởng + Hũ trên Tổng quan.

  GET  /che-do-thuong?ky=            cấu hình hiệu lực của kỳ + lịch sử (admin/kế toán)
  PUT  /che-do-thuong                lưu phiên bản mới — áp từ kỳ sau (admin)
  GET  /che-do-thuong/xem-thu?ky=    bảng thưởng dự kiến (admin/kế toán)
  POST /che-do-thuong/chot?ky=       chốt kỳ → Bonus chờ duyệt + 1 đơn duyệt (admin/kế toán)
  GET/PUT /che-do-thuong/loai-tru?ky= danh sách bị kỷ luật trong kỳ (admin/kế toán)
  GET  /che-do-thuong/hu             hũ doanh số cho Tổng quan (theo «Ai thấy hũ»)
  GET  /che-do-thuong/cua-toi        điểm JAMA + khoản dự kiến của chính mình
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import cache
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.services import che_do_thuong as cdt
from app.services.attendance_service import get_setting_json, set_setting_json
from app.services.audit import log_action

router = APIRouter(prefix="/che-do-thuong", tags=["che-do-thuong"])

TTL_BANG = 120
TTL_HU = 60


def _quan_tri(u: User) -> None:
    if u.role not in ("admin", "accountant"):
        raise HTTPException(403, "Chỉ Admin hoặc Kế toán xem được Chế độ thưởng")


def _ky(ky: str | None) -> str:
    try:
        return cdt.kiem_tra_ky(ky or cdt.ky_hien_tai())
    except ValueError as e:
        raise HTTPException(400, str(e))


def xoa_cache() -> None:
    cache.clear_prefix("cdt:")


async def _bang(db: AsyncSession, ky: str) -> dict:
    key = f"cdt:bang:{ky}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    kq = await cdt.tinh_bang_thuong(db, ky)
    cache.set(key, kq, TTL_BANG)
    return kq


@router.get("")
async def xem_cau_hinh(
    ky: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _quan_tri(user)
    ky = _ky(ky)
    cfg, hieu_luc = await cdt.doc_cau_hinh(db, ky)
    kho = await cdt.doc_kho(db)
    hien_tai = cdt.ky_hien_tai()
    return {
        "ky": ky,
        "cau_hinh": cfg,
        "hieu_luc_tu": hieu_luc,
        "phien_ban": sorted(kho["phien_ban"]),
        "lich_su": list(reversed(kho["lich_su"]))[:20],
        "lan_luu_sau_ap_tu": hien_tai if not kho["phien_ban"] else cdt.ky_sau(hien_tai),
        "mac_dinh": cdt.CAU_HINH_MAC_DINH,
    }


class CauHinhIn(BaseModel):
    cau_hinh: dict


@router.put("")
async def luu_cau_hinh(
    body: CauHinhIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "admin":
        raise HTTPException(403, "Chỉ Admin sửa được Chế độ thưởng")
    truoc, _ = await cdt.doc_cau_hinh(db, cdt.ky_sau(cdt.ky_hien_tai()))
    sach, hieu_luc = await cdt.luu_cau_hinh(db, body.cau_hinh, user)
    await log_action(db, actor=user, action="che_do_thuong.luu", entity_type="che_do_thuong",
                     entity_id=hieu_luc, before=truoc, after=sach)
    xoa_cache()
    return {"cau_hinh": sach, "hieu_luc_tu": hieu_luc}


@router.get("/xem-thu")
async def xem_thu(
    ky: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _quan_tri(user)
    return await _bang(db, _ky(ky))


@router.post("/chot")
async def chot(
    ky: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _quan_tri(user)
    ky = _ky(ky)
    try:
        kq = await cdt.chot_ky(db, ky, user)
    except cdt.LoiChot as e:
        raise HTTPException(e.status_code, e.detail)
    xoa_cache()
    return kq


class LoaiTruIn(BaseModel):
    user_ids: list[str] = Field(default_factory=list, max_length=200)
    ly_do: dict[str, str] = Field(default_factory=dict)


@router.get("/loai-tru")
async def xem_loai_tru(
    ky: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _quan_tri(user)
    ky = _ky(ky)
    v = await get_setting_json(db, cdt.KEY_LOAI_TRU.format(ky=ky))
    return {"ky": ky, "user_ids": v.get("user_ids") or [], "ly_do": v.get("ly_do") or {}}


@router.put("/loai-tru")
async def luu_loai_tru(
    body: LoaiTruIn,
    ky: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _quan_tri(user)
    ky = _ky(ky)
    if (await get_setting_json(db, cdt.KEY_DA_CHOT.format(ky=ky))).get("luc"):
        raise HTTPException(409, f"Kỳ {ky} đã chốt — không sửa danh sách được nữa")
    ids = list(dict.fromkeys(body.user_ids))
    if ids:
        co = set((await db.execute(select(User.id).where(User.id.in_(ids)))).scalars().all())
        ids = [i for i in ids if i in co]
    v = {"user_ids": ids, "ly_do": {k: str(t)[:200] for k, t in body.ly_do.items() if k in ids}}
    await set_setting_json(db, cdt.KEY_LOAI_TRU.format(ky=ky), v)
    await log_action(db, actor=user, action="che_do_thuong.loai_tru", entity_type="che_do_thuong",
                     entity_id=ky, after=v)
    xoa_cache()
    return {"ky": ky, **v}


@router.get("/hu")
async def hu_doanh_so(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Hũ cho Tổng quan. Ai không được xem → {"hien": false} (không 403 để FE ẩn êm)."""
    ky = cdt.ky_hien_tai()
    cfg, _ = await cdt.doc_cau_hinh(db, ky)
    hu_cfg = cfg["chuong_trinh"]["hu_doanh_so"]
    if not hu_cfg["bat"] or not cdt.duoc_xem_hu(user, hu_cfg):
        return {"hien": False}
    key = f"cdt:hu:{ky}"
    data = cache.get(key)
    if data is None:
        data = await cdt.du_lieu_hu(db, ky)
        cache.set(key, data, TTL_HU)
    return {"hien": True, **data}


@router.get("/cua-toi")
async def cua_toi(
    ky: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ky = _ky(ky)
    cfg, _ = await cdt.doc_cau_hinh(db, ky)
    if not cfg["dieu_kien"]["nv_xem_diem"] and user.role not in ("admin", "accountant"):
        return {"hien": False}
    bang = await _bang(db, ky)
    dong = next((r for r in bang["nguoi"] if r["user_id"] == user.id), None)
    if dong is None:
        return {"hien": False}
    return {
        "hien": True, "ky": ky, "quy": bang["quy"], "cuoi_quy": bang["cuoi_quy"],
        "he_so_bang": cfg["diem_jama"]["he_so"],
        "trong_so": cfg["diem_jama"]["trong_so"].get(user.department or "")
        or cfg["diem_jama"]["trong_so"].get("_khac"),
        **{k: dong[k] for k in ("diem", "he_so", "thanh_phan", "chi_tiet", "khoan", "tong",
                                 "du_kien_cuoi_quy", "ghi_chu")},
    }


@router.get("/nguoi/{user_id}")
async def diem_nguoi(
    user_id: str,
    ky: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Điểm JAMA của một nhân viên — cho Hồ sơ 360° (chính chủ hoặc admin/kế toán)."""
    if user.id != user_id and user.role not in ("admin", "accountant"):
        raise HTTPException(403, "Không có quyền xem điểm người khác")
    ky = _ky(ky)
    cfg, _ = await cdt.doc_cau_hinh(db, ky)
    if user.id == user_id and not cfg["dieu_kien"]["nv_xem_diem"] and user.role not in ("admin", "accountant"):
        return {"hien": False}
    bang = await _bang(db, ky)
    dong = next((r for r in bang["nguoi"] if r["user_id"] == user_id), None)
    if dong is None:
        return {"hien": False}
    return {"hien": True, "ky": ky, "quy": bang["quy"], **dong}
