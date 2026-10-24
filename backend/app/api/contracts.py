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
from app.schemas.contract import ContractCreate, ContractUpdate, ContractResponse, PaymentUpdate

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
    return ContractResponse.model_validate(contract)


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
    for k, v in data.model_dump(exclude_unset=True).items():
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

    await db.flush()
    return ContractResponse.model_validate(contract)


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

    da_thu_truoc = installments[installment_idx].get("status") == "paid"
    installments[installment_idx]["status"] = data.status
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
    if data.status == "paid":
        await hoa_hong.khi_thu_tien(db, contract, installment_idx)
    elif da_thu_truoc:
        await hoa_hong.khi_bo_thu_tien(db, contract, installment_idx)

    await db.flush()
    return ContractResponse.model_validate(contract)

