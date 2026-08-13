"""Accounting API — transactions, commissions, payroll."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.permissions import quyen_hieu_luc, yeu_cau
from app.models.user import User
from app.models.payroll import Transaction, Commission, Payroll
from app.schemas.accounting import (
    TransactionCreate, TransactionUpdate, CommissionCreate, CommissionStatusUpdate,
)
from app.cache import cache

router = APIRouter(prefix="/accounting", tags=["accounting"])


@router.get("/transactions")
async def list_transactions(
    type: str | None = None,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
    # Sổ giao dịch chứa cả dòng Lương/Hoa hồng kèm tên người nhận — đây là dữ liệu
    # P&L, gác theo ô «Xem Lợi nhuận (P&L)» trên trang Phân quyền. Trước 13/08/2026
    # gác bằng danh sách role viết cứng (có cả data_entry) nên sale đọc được lương người khác.
    current_user: User = Depends(yeu_cau("canViewPnL")),
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

    # Join tên nhân viên liên quan (giao dịch Lương/Hoa hồng) — 1 query cho cả trang
    related_ids = {t.related_user_id for t in txns if t.related_user_id}
    user_names: dict[str, str] = {}
    if related_ids:
        rows = await db.execute(select(User.id, User.full_name).where(User.id.in_(related_ids)))
        user_names = {uid: name for uid, name in rows.all()}

    return {
        "items": [
            {
                "id": t.id, "code": t.code, "type": t.type, "category": t.category,
                "description": t.description, "amount": t.amount,
                "project_id": t.project_id, "status": t.status,
                "related_user_id": t.related_user_id,
                "related_user_name": user_names.get(t.related_user_id) if t.related_user_id else None,
                "date": str(t.date), "created_at": str(t.created_at),
            }
            for t in txns
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


# Lưu ý: bản cũ có @cached đặt TRÊN @router.get — decorator áp từ dưới lên nên
# router đã đăng ký hàm gốc, cache không bao giờ chạy cho request thật. Gỡ luôn
# cho khỏi tưởng nhầm là có cache.
@router.get("/summary")
async def accounting_summary(
    db: AsyncSession = Depends(get_db),
    # Tổng thu/chi/lãi ròng toàn công ty = P&L. Trước 13/08/2026 KHÔNG có gác —
    # ai đăng nhập cũng gọi được.
    current_user: User = Depends(yeu_cau("canViewPnL")),
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
    # Trước 13/08/2026 endpoint này KHÔNG có gác — mọi người đăng nhập đều thấy
    # hoa hồng của TẤT CẢ nhân viên kèm tên. Nay: cần «Xem Kế toán», và nếu chưa
    # được cấp «Xem hoa hồng người khác» thì máy chủ chỉ trả hoa hồng của chính mình
    # (bản cũ chỉ lọc trên giao diện — F12 là thấy hết).
    perms = await quyen_hieu_luc(current_user, db)
    if not perms.get("canViewAccounting"):
        raise HTTPException(
            status_code=403,
            detail="Bạn chưa được cấp quyền «Xem Kế toán». "
                   "Nếu công việc cần, nhờ quản trị viên mở quyền này trên trang Phân quyền.",
        )
    q = (
        select(Commission, User.full_name)
        .outerjoin(User, Commission.user_id == User.id)
        .order_by(Commission.created_at.desc())
    )
    if not perms.get("canViewCommissionOthers"):
        q = q.where(Commission.user_id == current_user.id)
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
    # Gác theo ô «Xem Lương» thay cho danh sách role viết cứng — mặc định vẫn
    # chỉ admin + kế toán, nhưng nay sếp bật/tắt được ngay trên trang Phân quyền.
    current_user: User = Depends(yeu_cau("canViewPayroll")),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List payroll entries."""
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
        related_user_id=str(data.user_id) if data.user_id else None,
        created_by=current_user.id,
        status="completed",
        # Tôn trọng ngày kế toán chọn (bản cũ bỏ qua, luôn lấy giờ hiện tại)
        date=datetime.combine(data.transaction_date, datetime.min.time()) if data.transaction_date else datetime.now(timezone.utc),
    )
    db.add(txn)
    await db.flush()
    cache.clear_prefix("accounting")
    return {
        "id": txn.id, "code": txn.code, "type": txn.type,
        "category": txn.category, "amount": txn.amount, "status": txn.status,
        "related_user_id": txn.related_user_id,
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
    # Kỳ lương đã khóa → cấm thêm hoa hồng lùi kỳ
    if data.period:
        from app.services.attendance_service import is_period_locked
        if await is_period_locked(db, data.period):
            raise HTTPException(status_code=409, detail=f"Kỳ lương {data.period} đã khóa — không thể thêm hoa hồng")
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
    # Kỳ lương đã khóa → cấm đổi trạng thái hoa hồng của kỳ đó
    if comm.period:
        from app.services.attendance_service import is_period_locked
        if await is_period_locked(db, comm.period):
            raise HTTPException(status_code=409, detail=f"Kỳ lương {comm.period} đã khóa — không thể sửa hoa hồng")
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
    # Trước 13/08/2026 KHÔNG có gác — ai đăng nhập cũng tải được toàn bộ sổ
    # giao dịch (kèm dòng lương) ra CSV. Cùng cửa với danh sách giao dịch.
    current_user: User = Depends(yeu_cau("canViewPnL")),
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

