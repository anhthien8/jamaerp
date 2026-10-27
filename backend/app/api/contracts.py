"""Contracts API — CRUD with payment milestone tracking."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import can_confirm_payment
from app.middleware.permissions import quyen_hieu_luc
from app.models.user import User
from app.models.contract import Contract
from app.schemas.contract import ContractCreate, ContractUpdate, ContractResponse, PaymentUpdate, LichThuUpdate, PhuLucCreate
from app.services.dong_bo_tai_chinh import dong_bo_gia_tri_du_an, ghi_giao_dich_thu

router = APIRouter(prefix="/contracts", tags=["contracts"])


async def _yeu_cau_quyen_hop_dong(nguoi: User, db: AsyncSession) -> None:
    """Tạo/sửa hợp đồng phải có ô «Tạo Hợp đồng» trong ma trận (22/10/2026).

    Trước đó backend không kiểm gì: frontend ẩn nút nhưng gọi API trực tiếp
    là tạo/sửa được hợp đồng — kể cả đổi `status` sang «signed» để sinh hoa hồng.
    """
    perms = await quyen_hieu_luc(nguoi, db)
    if not perms.get("canCreateContracts"):
        raise HTTPException(status_code=403, detail="Bạn không có quyền «Tạo Hợp đồng» — xem trang Phân quyền")


@router.get("")
async def list_contracts(
    status: str | None = None,
    project_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List contracts."""
    q = select(Contract).order_by(Contract.created_at.desc())
    if status:
        q = q.where(Contract.status == status)
    if project_id:
        q = q.where(Contract.project_id == project_id)

    # Count total (before pagination)
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    contracts = result.scalars().all()

    return {
        "items": [ContractResponse.model_validate(c) for c in contracts],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get contract detail."""
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Hợp đồng không tồn tại")
    return ContractResponse.model_validate(contract)


@router.post("", response_model=ContractResponse)
async def create_contract(
    data: ContractCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create new contract with default 4-installment payment terms."""
    await _yeu_cau_quyen_hop_dong(current_user, db)
    contract = Contract(
        code=data.code,
        project_id=str(data.project_id),
        title=data.title,
        total_value=data.total_value,
        signed_date=data.signed_date,
        working_days=data.working_days,
        start_date=data.start_date,
        notes=data.notes,
        contract_kind=data.contract_kind,
        status="draft",
        payment_terms={
            "installments": [
                {"name": "Đợt 1 (Đặt cọc)", "percentage": 25, "milestone": "signing", "status": "pending"},
                {"name": "Đợt 2 (Nghiệm thu thô)", "percentage": 25, "milestone": "rough_complete", "status": "pending"},
                {"name": "Đợt 3 (Nghiệm thu nội thất)", "percentage": 25, "milestone": "interior_complete", "status": "pending"},
                {"name": "Đợt 4 (Bàn giao)", "percentage": 25, "milestone": "handover", "status": "pending"},
            ]
        },
    )
    db.add(contract)
    await db.flush()
    await dong_bo_gia_tri_du_an(db, contract.project_id)
    from app.cache import cache
    cache.clear_prefix("pl")  # P&L tính doanh thu theo đợt đã thu
    return ContractResponse.model_validate(contract)


@router.post("/{contract_id}/phu-luc", response_model=ContractResponse)
async def tao_phu_luc(
    contract_id: str,
    data: PhuLucCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Phụ lục phát sinh/giảm trừ: HĐ con, 1 đợt thu, giá trị dự án tự cộng (27/10/2026)."""
    await _yeu_cau_quyen_hop_dong(current_user, db)
    goc = await db.get(Contract, contract_id)
    if not goc:
        raise HTTPException(404, "Không tìm thấy hợp đồng")
    if goc.parent_contract_id:
        raise HTTPException(400, "Thêm phụ lục vào hợp đồng gốc, không vào phụ lục")
    if goc.status == "cancelled":
        raise HTTPException(400, "Hợp đồng đã huỷ")
    so = (await db.execute(select(func.count()).select_from(Contract)
                           .where(Contract.parent_contract_id == goc.id))).scalar() or 0
    pl = Contract(
        code=f"{goc.code}-PL{so + 1}"[:40], project_id=goc.project_id, title=data.title,
        total_value=data.total_value, notes=data.notes, contract_kind=goc.contract_kind,
        parent_contract_id=goc.id, status="draft",
        payment_terms={"installments": [] if data.total_value <= 0 else [
            {"name": "Thu phụ lục", "percentage": 100, "milestone": "signing", "status": "pending"}]},
    )
    db.add(pl)
    await db.flush()
    await dong_bo_gia_tri_du_an(db, goc.project_id)
    from app.cache import cache
    cache.clear_prefix("pl")
    return ContractResponse.model_validate(pl)


@router.put("/{contract_id}", response_model=ContractResponse)
async def update_contract(
    contract_id: str,
    data: ContractUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update contract."""
    await _yeu_cau_quyen_hop_dong(current_user, db)
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Hợp đồng không tồn tại")

    old_status = contract.status
    moi = data.model_dump(exclude_unset=True)
    st_moi = moi.get("status")
    if st_moi and st_moi != old_status:
        # Audit 27/10: HĐ đã nghiệm thu/huỷ mà đổi trạng thái lại → ký lại sinh hoa hồng lần 2
        if old_status in ("completed", "cancelled"):
            raise HTTPException(status_code=400, detail="Hợp đồng đã nghiệm thu hoặc đã huỷ — không đổi trạng thái được nữa")
        if st_moi == "draft" and any(
            d.get("status") in ("paid", "partial") for d in (contract.payment_terms or {}).get("installments", [])
        ):
            raise HTTPException(status_code=400, detail="Hợp đồng đã có đợt thu tiền — không quay về nháp được")
    for k, v in moi.items():
        setattr(contract, k, v)
    contract.updated_at = datetime.now(timezone.utc)

    # Hoa hồng theo JD (24/10/2026) — thay bản cũ cộng cứng 3% thiết kế / 2% thi
    # công cho sale ngay lúc ký. Nay sale ăn theo TỪNG ĐỢT khách trả (update_payment);
    # lúc ký chỉ tính phần thu mua/báo giá, lúc nghiệm thu tính giám sát + phần còn lại.
    new_status = contract.status
    if new_status != old_status:
        from app.services import hoa_hong
        if new_status == "signed":
            await hoa_hong.khi_ky_hop_dong(db, contract)
        elif new_status == "completed":
            await hoa_hong.khi_nghiem_thu(db, contract)
        elif new_status == "cancelled":
            await _thu_hoi_khi_huy(db, contract)

    await db.flush()
    # Giá trị HĐ đổi → dự án đổi theo (Hũ thưởng, Bảng KD đọc giá trị dự án)
    await dong_bo_gia_tri_du_an(db, contract.project_id)
    from app.cache import cache
    cache.clear_prefix("pl")  # P&L tính doanh thu theo đợt đã thu
    return ContractResponse.model_validate(contract)


async def _thu_hoi_khi_huy(db: AsyncSession, contract: Contract) -> None:
    """Huỷ HĐ (audit 27/10): gỡ hoa hồng chưa duyệt, huỷ giao dịch thu tự sinh.
    Hoa hồng đã duyệt/đã trả giữ nguyên để kế toán xử lý tay (không tự đảo lương)."""
    from app.models.payroll import Commission
    from app.models.payroll import Transaction
    for c in (await db.execute(select(Commission).where(
        Commission.contract_id == contract.id, Commission.status.in_(("cho_moc", "pending"))
    ))).scalars().all():
        await db.delete(c)
    for gd in (await db.execute(select(Transaction).where(
        Transaction.code.like(f"THU-{contract.code}-D%")
    ))).scalars().all():
        gd.status = "cancelled"


@router.put("/{contract_id}/payments/{installment_idx}")
async def update_payment(
    contract_id: str,
    installment_idx: int,
    data: PaymentUpdate = PaymentUpdate(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update payment installment status."""
    # Ghi nhận tiền về = việc kế toán. Trước QC 29/08 mọi tài khoản xem được hợp
    # đồng đều tích được «đã thu tiền» (backend không kiểm, FE không ẩn nút).
    if not can_confirm_payment(current_user):
        raise HTTPException(status_code=403, detail="Chỉ Kế toán / Giám đốc / Trưởng nhóm được xác nhận đã thu tiền")
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Hợp đồng không tồn tại")

    terms = contract.payment_terms or {"installments": []}
    installments = terms.get("installments", [])
    if installment_idx < 0 or installment_idx >= len(installments):
        raise HTTPException(status_code=400, detail="Đợt thanh toán không hợp lệ")

    if data.status not in ("pending", "paid", "partial"):
        raise HTTPException(status_code=400, detail="Trạng thái đợt không hợp lệ")
    if data.status == "partial" and not data.amount:
        raise HTTPException(status_code=400, detail="Thu một phần cần nhập số tiền đã thu")
    if contract.status == "cancelled":
        raise HTTPException(status_code=400, detail="Hợp đồng đã huỷ — không ghi thu được")
    da_thu_truoc = installments[installment_idx].get("status") == "paid"
    installments[installment_idx]["status"] = data.status
    if data.status != "partial" and not data.amount:
        # Thu nốt sau khi đã thu một phần / bỏ thu: bỏ số tạm cũ, tính lại theo % HĐ
        installments[installment_idx].pop("amount", None)
    if data.paid_date:
        installments[installment_idx]["paid_date"] = str(data.paid_date)
    else:
        installments[installment_idx]["paid_date"] = str(datetime.now(timezone.utc).date())
    if data.amount:
        installments[installment_idx]["amount"] = data.amount
    if data.evidence_url:
        installments[installment_idx]["proof_image"] = data.evidence_url

    terms["installments"] = installments
    contract.payment_terms = terms
    contract.updated_at = datetime.now(timezone.utc)

    # Mark as modified for SQLAlchemy to detect
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(contract, "payment_terms")
    await db.flush()

    # Hoa hồng theo đợt khách trả (services/hoa_hong.py)
    from app.services import hoa_hong
    if contract.status == "draft" and data.status in ("paid", "partial"):
        # Khách đã trả tiền = HĐ đã ký (audit 27/10: HĐ nháp thu tiền không vào phải thu)
        contract.status = "signed"
        await hoa_hong.khi_ky_hop_dong(db, contract)
    if data.status == "paid":
        await hoa_hong.khi_thu_tien(db, contract, installment_idx)
    elif da_thu_truoc:
        await hoa_hong.khi_bo_thu_tien(db, contract, installment_idx)
    # Tiền về → giao dịch thu ở Tài chính (kế toán khỏi nhập lại)
    await ghi_giao_dich_thu(db, contract, installment_idx, current_user.id)
    from app.cache import cache as _c
    _c.clear_prefix("accounting")

    await db.flush()
    from app.cache import cache
    cache.clear_prefix("pl")  # P&L tính doanh thu theo đợt đã thu
    return ContractResponse.model_validate(contract)



@router.put("/{contract_id}/lich-thu", response_model=ContractResponse)
async def update_lich_thu(
    contract_id: str,
    data: LichThuUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sửa lịch thu (27/10/2026): số đợt, %, hạn thu. Bản cũ đóng cứng 4×25% không hạn.

    Giữ nguyên trạng thái/tiền/chứng từ của các đợt đã có theo thứ tự; đợt đã thu
    không được bỏ đi.
    """
    await _yeu_cau_quyen_hop_dong(current_user, db)
    contract = await db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Hợp đồng không tồn tại")
    if abs(sum(d.percentage for d in data.dot) - 100) > 0.01:
        raise HTTPException(status_code=400, detail="Tổng % các đợt phải bằng 100")
    cu = (contract.payment_terms or {}).get("installments") or []
    if any((x or {}).get("status") in ("paid", "partial") for x in cu[len(data.dot):]):
        raise HTTPException(status_code=400, detail="Không bỏ được đợt đã thu tiền")
    moi = []
    for i, d in enumerate(data.dot):
        inst = dict(cu[i]) if i < len(cu) else {"status": "pending"}
        inst.update({"name": d.name.strip()[:120] or f"Đợt {i + 1}", "percentage": d.percentage,
                     "due_date": d.due_date.isoformat() if d.due_date else None})
        if d.milestone:
            inst["milestone"] = d.milestone
        moi.append(inst)
    contract.payment_terms = {**(contract.payment_terms or {}), "installments": moi}
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(contract, "payment_terms")
    contract.updated_at = datetime.now(timezone.utc)
    await db.flush()
    from app.cache import cache
    cache.clear_prefix("pl")
    return ContractResponse.model_validate(contract)


# ── Tệp hợp đồng đã ký (26/10/2026) ───────────────────────────────────────
# Xem/tải: ô «Xem Hợp đồng». Đính kèm: ô «Tạo Hợp đồng». Gỡ: người tải lên,
# BGĐ hoặc Kế toán (ẩn, không xoá cứng).

from pathlib import PurePath
from urllib.parse import quote

from fastapi import File, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import defer

from app.middleware.permissions import yeu_cau
from app.models.contract_file import ContractFile

TEP_HD_TOI_DA = 40 * 1024 * 1024
TEP_HD_DUOI = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


def _tep_dict(f: ContractFile) -> dict:
    return {
        "id": f.id, "filename": f.filename, "mime": f.mime, "size_bytes": f.size_bytes,
        "uploaded_by": f.uploaded_by,
        "uploaded_by_name": f.uploaded_by_name,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


async def _lay_hd(db: AsyncSession, contract_id: str) -> Contract:
    hd = await db.get(Contract, contract_id)
    if not hd:
        raise HTTPException(status_code=404, detail="Hợp đồng không tồn tại")
    return hd


@router.get("/{contract_id}/files")
async def list_contract_files(
    contract_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(yeu_cau("canViewContracts")),
):
    await _lay_hd(db, contract_id)
    rows = (await db.execute(
        select(ContractFile).options(defer(ContractFile.data))
        .where(ContractFile.contract_id == contract_id, ContractFile.is_active.is_(True))
        .order_by(ContractFile.created_at.desc())
    )).scalars().all()
    return {"items": [_tep_dict(f) for f in rows]}


@router.post("/{contract_id}/files", status_code=201)
async def upload_contract_files(
    contract_id: str,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _yeu_cau_quyen_hop_dong(current_user, db)
    await _lay_hd(db, contract_id)
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Mỗi lượt tối đa 10 tệp")
    goi = []
    for f in files:
        ten = PurePath(f.filename or "").name
        duoi = PurePath(ten).suffix.lower()
        if duoi not in TEP_HD_DUOI:
            raise HTTPException(status_code=400, detail=f"«{ten}»: chỉ nhận PDF, Word hoặc ảnh chụp")
        data = await f.read()
        if not data:
            raise HTTPException(status_code=400, detail=f"«{ten}» rỗng")
        if len(data) > TEP_HD_TOI_DA:
            raise HTTPException(status_code=413, detail=f"«{ten}» quá 40 MB")
        goi.append((ten, TEP_HD_DUOI[duoi], data))
    ra = []
    for ten, mime, data in goi:
        m = ContractFile(contract_id=contract_id, filename=ten, mime=mime, data=data, size_bytes=len(data),
                         uploaded_by=current_user.id, uploaded_by_name=current_user.full_name)
        db.add(m)
        await db.flush()
        ra.append(_tep_dict(m))
    await db.commit()
    return {"items": ra}


@router.get("/{contract_id}/files/{file_id}/download")
async def download_contract_file(
    contract_id: str,
    file_id: str,
    inline: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(yeu_cau("canViewContracts")),
):
    f = await db.get(ContractFile, file_id)
    if not f or f.contract_id != contract_id or not f.is_active:
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp")
    kieu = "inline" if inline else "attachment"
    return Response(content=f.data, media_type=f.mime, headers={
        "Content-Disposition": f"{kieu}; filename*=UTF-8''{quote(f.filename)}",
        "Cache-Control": "private, no-store",
    })


@router.delete("/{contract_id}/files/{file_id}")
async def remove_contract_file(
    contract_id: str,
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    f = await db.get(ContractFile, file_id)
    if not f or f.contract_id != contract_id or not f.is_active:
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp")
    if current_user.role not in ("admin", "accountant") and f.uploaded_by != current_user.id:
        raise HTTPException(status_code=403, detail="Chỉ người tải lên, BGĐ hoặc Kế toán được gỡ tệp")
    f.is_active = False
    await db.commit()
    return {"ok": True}
