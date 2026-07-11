"""Accounting API — transactions, commissions, payroll."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.payroll import Transaction, Commission, Payroll
from app.schemas.accounting import (
    TransactionCreate, TransactionUpdate, CommissionCreate, CommissionStatusUpdate,
)
from app.cache import cache, cached

router = APIRouter(prefix="/accounting", tags=["accounting"])


@router.get("/transactions")
async def list_transactions(
    type: str | None = None,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List transactions."""
    q = select(Transaction).order_by(Transaction.date.desc())
    if type:
        q = q.where(Transaction.type == type)
    if category:
        q = q.where(Transaction.category == category)

    # Count total (before pagination)
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    txns = result.scalars().all()

    return {
        "items": [
            {
                "id": t.id, "code": t.code, "type": t.type, "category": t.category,
                "description": t.description, "amount": t.amount,
                "project_id": t.project_id, "status": t.status,
                "date": str(t.date), "created_at": str(t.created_at),
            }
            for t in txns
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@cached(ttl=300, prefix="accounting")
@router.get("/summary")
async def accounting_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Financial summary."""
    income = (await db.execute(
        select(func.sum(Transaction.amount)).where(
            Transaction.type == "income",
            Transaction.status != "cancelled"
        )
    )).scalar() or 0
    expense = (await db.execute(
        select(func.sum(Transaction.amount)).where(
            Transaction.type == "expense",
            Transaction.status != "cancelled"
        )
    )).scalar() or 0

    # By category (exclude cancelled)
    cat_q = select(
        Transaction.category, Transaction.type,
        func.sum(Transaction.amount), func.count(Transaction.id)
    ).where(Transaction.status != "cancelled").group_by(Transaction.category, Transaction.type)
    cat_result = await db.execute(cat_q)
    by_category = [
        {"category": cat, "type": t, "total": total, "count": count}
        for cat, t, total, count in cat_result.all()
    ]

    return {
        "total_income": income,
        "total_expense": expense,
        "net": income - expense,
        "by_category": by_category,
    }


@router.get("/commissions")
async def list_commissions(
    period: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List commissions."""
    q = (
        select(Commission, User.full_name)
        .outerjoin(User, Commission.user_id == User.id)
        .order_by(Commission.created_at.desc())
    )
    if period:
        q = q.where(Commission.period == period)

    # Count total (before pagination)
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)

    return {
        "items": [
            {
                "id": c.id, "user_id": c.user_id, "user_name": name,
                "project_id": c.project_id, "type": c.type,
                "rate": c.rate, "base_amount": c.base_amount,
                "commission_amount": c.commission_amount,
                "milestone": c.milestone, "status": c.status,
                "period": c.period,
            }
            for c, name in result.all()
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/payroll")
async def list_payroll(
    period: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List payroll entries — admin/accountant only."""
    if current_user.role not in ("admin", "accountant"):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập bảng lương")
    q = (
        select(Payroll, User.full_name)
        .outerjoin(User, Payroll.user_id == User.id)
        .order_by(Payroll.created_at.desc())
    )
    if period:
        q = q.where(Payroll.period == period)

    # Count total (before pagination)
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)

    return {
        "items": [
            {
                "id": p.id, "user_id": p.user_id, "user_name": name,
                "period": p.period, "base_salary": p.base_salary,
                "commission_total": p.commission_total, "bonus": p.bonus,
                "deductions": p.deductions, "net_salary": p.net_salary,
                "status": p.status,
            }
            for p, name in result.all()
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


# --- CRUD Endpoints ---

@router.post("/transactions")
async def create_transaction(
    data: TransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create new transaction."""
    if current_user.role not in ("admin", "accountant"):
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện thao tác này")
    import uuid
    txn = Transaction(
        id=str(uuid.uuid4()),
        code=f"TXN-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        type=data.type,
        category=data.category,
        description=data.description or "",
        amount=data.amount,
        project_id=str(data.project_id) if data.project_id else None,
        created_by=current_user.id,
        status="completed",
        date=datetime.now(timezone.utc),
    )
    db.add(txn)
    await db.flush()
    cache.clear_prefix("accounting")
    return {
        "id": txn.id, "code": txn.code, "type": txn.type,
        "category": txn.category, "amount": txn.amount, "status": txn.status,
    }


@router.put("/transactions/{txn_id}")
async def update_transaction(
    txn_id: str,
    data: TransactionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update transaction."""
    if current_user.role not in ("admin", "accountant"):
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện thao tác này")
    result = await db.execute(select(Transaction).where(Transaction.id == txn_id))
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(status_code=404, detail="Giao dịch không tồn tại")

    update_fields = data.model_dump(exclude_unset=True)
    for k, v in update_fields.items():
        setattr(txn, k, v)
    await db.flush()
    cache.clear_prefix("accounting")
    return {"id": txn.id, "code": txn.code, "status": txn.status, "amount": txn.amount}


@router.delete("/transactions/{txn_id}")
async def delete_transaction(
    txn_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete transaction (set status=cancelled)."""
    if current_user.role not in ("admin", "accountant"):
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện thao tác này")
    result = await db.execute(select(Transaction).where(Transaction.id == txn_id))
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(status_code=404, detail="Giao dịch không tồn tại")
    txn.status = "cancelled"
    await db.flush()
    cache.clear_prefix("accounting")
    return {"id": txn.id, "status": "cancelled"}


@router.post("/commissions")
async def create_commission(
    data: CommissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create commission record."""
    if current_user.role not in ("admin", "accountant"):
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện thao tác này")
    import uuid
    comm = Commission(
        id=str(uuid.uuid4()),
        user_id=str(data.user_id),
        project_id=str(data.project_id) if data.project_id else None,
        lead_id=str(data.lead_id) if data.lead_id else None,
        type=data.type,
        rate=data.rate,
        base_amount=data.base_amount,
        commission_amount=data.base_amount * data.rate,
        milestone=data.milestone,
        milestone_pct=data.milestone_pct,
        status=data.status,
        period=data.period,
    )
    db.add(comm)
    await db.flush()
    return {
        "id": comm.id, "user_id": comm.user_id,
        "commission_amount": comm.commission_amount, "status": comm.status,
    }


@router.put("/commissions/{comm_id}")
async def update_commission_status(
    comm_id: str,
    data: CommissionStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update commission status."""
    if current_user.role not in ("admin", "accountant"):
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện thao tác này")
    result = await db.execute(select(Commission).where(Commission.id == comm_id))
    comm = result.scalar_one_or_none()
    if not comm:
        raise HTTPException(status_code=404, detail="Hoa hồng không tồn tại")
    if data.status is not None:
        comm.status = data.status
    await db.flush()
    return {"id": comm.id, "status": comm.status}


# ── CSV Export ───────────────────────────────────────────────────────────

import csv
import io
from datetime import datetime, timezone
from fastapi.responses import StreamingResponse


@router.get("/transactions/export")
async def export_transactions_csv(
    type: str | None = None,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export transactions as CSV."""
    from app.models.payroll import Transaction
    q = select(Transaction).order_by(Transaction.date.desc())
    if type:
        q = q.where(Transaction.type == type)
    if category:
        q = q.where(Transaction.category == category)

    result = await db.execute(q)
    txns = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Mã", "Loại", "Danh mục", "Mô tả", "Số tiền", "Trạng thái", "Ngày"])
    for t in txns:
        writer.writerow([
            t.code, t.type, t.category, t.description,
            t.amount, t.status,
            t.date.strftime("%d/%m/%Y") if t.date else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=transactions_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"},
    )

