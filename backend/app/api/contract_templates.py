"""Thư viện mẫu hợp đồng / biên bản (25/10/2026).

- Ai có ô «Xem Hợp đồng» → xem danh sách + tải mẫu về.
- Chỉ BGĐ (admin) và Kế toán tải lên / thay bản mới / ẩn mẫu: mẫu là văn bản
  pháp lý dùng chung, sửa nhầm là cả công ty ký theo bản sai.
- Tải lên lại tệp cùng tên → thay bản cũ, tăng số phiên bản (không nhân đôi).
"""

import unicodedata
from datetime import datetime, timezone
from pathlib import PurePath
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.permissions import yeu_cau
from app.models.contract_template import ContractTemplate
from app.models.user import User

router = APIRouter(prefix="/contract-templates", tags=["contract-templates"])

TOI_DA_BYTES = 40 * 1024 * 1024  # PL02 phạm vi thi công ~34 MB
TOI_DA_TEP_MOT_LUOT = 20
DUOI_CHO_PHEP = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".pdf": "application/pdf",
}
VAI_QUAN_LY = ("admin", "accountant")


def _bo_dau(s: str) -> str:
    s = s.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn").lower()


def khoa_tep(filename: str) -> str:
    """«JAMA - HỢP ĐỒNG THI CÔNG NỘI THẤT.docx» → «jamahopdongthicongnoithat»."""
    return "".join(ch for ch in _bo_dau(PurePath(filename).stem) if ch.isalnum())[:200]


def phan_loai(filename: str) -> tuple[str, str, str | None]:
    """Đoán (tên hiển thị, nhóm, loại HĐ) từ tên tệp — người quản lý sửa lại được."""
    goc = PurePath(filename).stem
    k = _bo_dau(goc)
    if "phu luc" in k or k.startswith("pl0"):
        nhom = "phu_luc"
    elif "bien ban" in k:
        nhom = "bien_ban"
    elif "thanh toan" in k:
        nhom = "thanh_toan"
    elif "hop dong" in k:
        nhom = "hop_dong"
    else:
        nhom = "khac"

    loai = None
    if nhom in ("hop_dong", "phu_luc"):
        if "thiet ke" in k:
            loai = "thiet_ke"
        elif "thi cong" in k or "vat tu" in k:
            loai = "thi_cong"

    # Tên đẹp: bỏ tiền tố «JAMA -», đuôi năm «_2026», chữ hoa → chữ thường câu
    ten = goc.strip()
    for tien_to in ("JAMA - ", "JAMA-", "JAMA "):
        if ten.upper().startswith(tien_to):
            ten = ten[len(tien_to):]
    for duoi in ("_2026", " - 2026", "-2026", " 2026"):
        if ten.endswith(duoi):
            ten = ten[: -len(duoi)]
    ten = " ".join(ten.replace("_", " ").split())
    if ten.isupper():
        ten = ten.lower()
        ten = ten[:1].upper() + ten[1:]
    return ten[:200] or "Mẫu không tên", nhom, loai


def _la_quan_ly(user: User) -> bool:
    return user.role in VAI_QUAN_LY


def _ra_dict(m: ContractTemplate) -> dict:
    return {
        "id": m.id,
        "name": m.name,
        "category": m.category,
        "contract_kind": m.contract_kind,
        "filename": m.filename,
        "mime": m.mime,
        "size_bytes": m.size_bytes,
        "version": m.version,
        "is_active": m.is_active,
        "updated_by_name": m.updated_by_name,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


@router.get("")
async def list_templates(
    include_hidden: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(yeu_cau("canViewContracts")),
):
    q = select(ContractTemplate).options(defer(ContractTemplate.data)).order_by(
        ContractTemplate.category, ContractTemplate.name
    )
    if not (include_hidden and _la_quan_ly(current_user)):
        q = q.where(ContractTemplate.is_active.is_(True))
    rows = (await db.execute(q)).scalars().all()
    return {"items": [_ra_dict(m) for m in rows], "can_manage": _la_quan_ly(current_user)}


@router.get("/{template_id}/download")
async def download_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(yeu_cau("canViewContracts")),
):
    m = await db.get(ContractTemplate, template_id)
    if not m or (not m.is_active and not _la_quan_ly(current_user)):
        raise HTTPException(status_code=404, detail="Không tìm thấy mẫu")
    return Response(
        content=m.data,
        media_type=m.mime,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(m.filename)}",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("", status_code=201)
async def upload_templates(
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _la_quan_ly(current_user):
        raise HTTPException(status_code=403, detail="Chỉ BGĐ và Kế toán được tải mẫu hợp đồng lên")
    if len(files) > TOI_DA_TEP_MOT_LUOT:
        raise HTTPException(status_code=400, detail=f"Mỗi lượt tối đa {TOI_DA_TEP_MOT_LUOT} tệp")

    # Kiểm hết trước khi ghi — tệp lỗi giữa chừng không để lại nửa thư viện
    goi: list[tuple[str, str, bytes]] = []
    for f in files:
        ten_tep = PurePath(f.filename or "").name
        duoi = PurePath(ten_tep).suffix.lower()
        if duoi not in DUOI_CHO_PHEP:
            raise HTTPException(status_code=400, detail=f"«{ten_tep}»: chỉ nhận Word, Excel hoặc PDF")
        data = await f.read()
        if not data:
            raise HTTPException(status_code=400, detail=f"«{ten_tep}» rỗng")
        if len(data) > TOI_DA_BYTES:
            raise HTTPException(status_code=413, detail=f"«{ten_tep}» quá 40 MB")
        goi.append((ten_tep, DUOI_CHO_PHEP[duoi], data))

    bay_gio = datetime.now(timezone.utc).replace(tzinfo=None)
    ket_qua, tao, thay = [], 0, 0
    for ten_tep, mime, data in goi:
        khoa = khoa_tep(ten_tep)
        cu = (await db.execute(
            select(ContractTemplate).where(ContractTemplate.file_key == khoa).limit(1)
        )).scalar_one_or_none()
        if cu:
            cu.filename, cu.mime, cu.data, cu.size_bytes = ten_tep, mime, data, len(data)
            cu.version += 1
            cu.is_active = True
            cu.updated_by_name = current_user.full_name
            cu.updated_at = bay_gio
            m, thay = cu, thay + 1
        else:
            ten, nhom, loai = phan_loai(ten_tep)
            m = ContractTemplate(
                name=ten, category=nhom, contract_kind=loai, file_key=khoa,
                filename=ten_tep, mime=mime, data=data, size_bytes=len(data),
                updated_by_name=current_user.full_name, created_at=bay_gio, updated_at=bay_gio,
            )
            db.add(m)
            tao += 1
        await db.flush()
        ket_qua.append(_ra_dict(m))
    await db.commit()
    return {"items": ket_qua, "created": tao, "replaced": thay}


class TemplatePatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    category: Literal["hop_dong", "bien_ban", "thanh_toan", "phu_luc", "khac"] | None = None
    contract_kind: Literal["thiet_ke", "thi_cong", ""] | None = None
    is_active: bool | None = None


@router.patch("/{template_id}")
async def update_template(
    template_id: str,
    body: TemplatePatch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _la_quan_ly(current_user):
        raise HTTPException(status_code=403, detail="Chỉ BGĐ và Kế toán được sửa mẫu hợp đồng")
    m = await db.get(ContractTemplate, template_id)
    if not m:
        raise HTTPException(status_code=404, detail="Không tìm thấy mẫu")
    if body.name is not None:
        m.name = body.name.strip()
    if body.category is not None:
        m.category = body.category
    if body.contract_kind is not None:
        m.contract_kind = body.contract_kind or None
    if body.is_active is not None:
        m.is_active = body.is_active
    m.updated_by_name = current_user.full_name
    m.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    return _ra_dict(m)
