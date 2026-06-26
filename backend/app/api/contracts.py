"""Contracts API — CRUD with payment milestone tracking."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.contract import Contract
from app.schemas.contract import ContractCreate, ContractUpdate, ContractResponse, PaymentUpdate

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get("", response_model=list[ContractResponse])
async def list_contracts(
    status: str | None = None,
    project_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List contracts."""
    q = select(Contract).order_by(Contract.created_at.desc())
    if status:
        q = q.where(Contract.status == status)
    if project_id:
        q = q.where(Contract.project_id == project_id)
    result = await db.execute(q)
    contracts = result.scalars().all()
    return [ContractResponse.model_validate(c) for c in contracts]


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
    contract = Contract(
        code=data.code,
        project_id=str(data.project_id),
        title=data.title,
        total_value=data.total_value,
        signed_date=data.signed_date,
        working_days=data.working_days,
        start_date=data.start_date,
        notes=data.notes,
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
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Hợp đồng không tồn tại")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(contract, k, v)
    contract.updated_at = datetime.now(timezone.utc)
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
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Hợp đồng không tồn tại")

    terms = contract.payment_terms or {"installments": []}
    installments = terms.get("installments", [])
    if installment_idx < 0 or installment_idx >= len(installments):
        raise HTTPException(status_code=400, detail="Đợt thanh toán không hợp lệ")

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
    return ContractResponse.model_validate(contract)

